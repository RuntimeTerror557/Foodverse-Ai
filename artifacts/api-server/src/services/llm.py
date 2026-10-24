"""Provider layer for Food Verse AI.

All model access goes through ``LLMClient.complete_json`` so the rest of the
backend never touches a vendor SDK. The default implementation talks to the
Anthropic Messages API over plain HTTPS (stdlib only) and forces structured
output through a single tool call, so every response is a JSON object that we
then validate ourselves (see ``validators.py``).

Secrets stay on the server: the key is read from the environment and is never
returned to the browser or written to logs.
"""
from __future__ import annotations

import json
import logging
import os
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Protocol

logger = logging.getLogger("food-verse.llm")

DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_BASE_URL = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"


class AIError(Exception):
    """Failure of an AI workflow, safe to show to the user (``message``)."""

    HTTP_STATUS = {
        "not_configured": 503,
        "invalid_input": 422,
        "rate_limited": 429,
        "timeout": 504,
        "upstream": 502,
        "bad_response": 502,
    }

    def __init__(self, code: str, message: str, *, retry_after: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retry_after = retry_after

    @property
    def http_status(self) -> int:
        return self.HTTP_STATUS.get(self.code, 502)

    def as_detail(self) -> dict[str, Any]:
        detail: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.retry_after is not None:
            detail["retryAfterSeconds"] = self.retry_after
        return detail


class LLMClient(Protocol):
    model: str

    def complete_json(
        self,
        *,
        system: str,
        content: list[dict[str, Any]],
        tool_name: str,
        tool_description: str,
        schema: dict[str, Any],
        max_tokens: int = 4096,
    ) -> dict[str, Any]: ...


@dataclass
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: bytes


HttpPost = Callable[[str, dict[str, str], bytes, float], HttpResponse]


def _urllib_post(url: str, headers: dict[str, str], body: bytes, timeout: float) -> HttpResponse:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed https base URL
            return HttpResponse(response.status, {k.lower(): v for k, v in response.headers.items()}, response.read())
    except urllib.error.HTTPError as error:
        return HttpResponse(error.code, {k.lower(): v for k, v in error.headers.items()}, error.read())
    except (socket.timeout, TimeoutError) as error:
        raise AIError("timeout", "The AI service took too long to respond. Please try again.") from error
    except urllib.error.URLError as error:
        if isinstance(error.reason, (socket.timeout, TimeoutError)):
            raise AIError("timeout", "The AI service took too long to respond. Please try again.") from error
        raise AIError("upstream", "The AI service could not be reached. Please try again shortly.") from error


def error_for(response: HttpResponse) -> AIError:
    retry_after: int | None = None
    raw = response.headers.get("retry-after")
    if raw and raw.isdigit():
        retry_after = int(raw)
    upstream_message = ""
    try:
        parsed = json.loads(response.body)
        if isinstance(parsed, list) and parsed:  # Gemini sometimes wraps errors in a list
            parsed = parsed[0]
        upstream_message = str(parsed.get("error", {}).get("message", ""))[:400]
    except (ValueError, TypeError, AttributeError):
        pass
    # The provider's message never contains our key; it is logged server-side only.
    logger.warning("AI provider returned HTTP %s: %s", response.status, upstream_message or "(no message)")
    lowered = upstream_message.lower()
    if "credit balance" in lowered or "billing" in lowered or "credits" in lowered or "quota" in lowered and response.status != 429:
        return AIError("not_configured", "The AI provider account has no credits or quota left. Add credits (or use a provider with a free tier), then try again.")
    if response.status == 429:
        return AIError("rate_limited", "The AI service is busy right now. Please wait a moment and try again.", retry_after=retry_after)
    if response.status in (401, 403):
        return AIError("not_configured", "The AI service rejected the server's API key. Check the key in .env.")
    if response.status == 404:
        return AIError("not_configured", "The configured AI model was not found for this account. Set FOODVERSE_AI_MODEL to a model your key can use.")
    if response.status == 413:
        return AIError("invalid_input", "The upload is too large for the AI service. Try a smaller or lower-resolution file.")
    if response.status == 400:
        if "image" in lowered:
            return AIError("invalid_input", "The AI service could not process this image. Try a clearer or smaller photo.")
        return AIError("upstream", "The AI service rejected the request. Check the server log for details.")
    return AIError("upstream", "The AI service is temporarily unavailable. Please try again.", retry_after=retry_after)



def post_with_retries(
    http_post: HttpPost, url: str, headers: dict[str, str], body: bytes, *, timeout: float, max_retries: int, sleep: Callable[[float], None],
) -> bytes:
    """POST with backoff on timeouts, 429 and 5xx. Returns the body of the first 200 response."""
    last_error: AIError | None = None
    for attempt in range(max_retries + 1):
        try:
            response = http_post(url, headers, body, timeout)
        except AIError as error:
            last_error = error
            if error.code in ("timeout", "upstream") and attempt < max_retries:
                sleep(1.5 * (attempt + 1))
                continue
            raise
        if response.status == 200:
            return response.body
        last_error = error_for(response)
        if response.status in (429, 500, 502, 503, 504, 529) and attempt < max_retries:
            sleep(min(float(last_error.retry_after or 1.5 * (attempt + 1)), 10.0))
            continue
        raise last_error
    raise last_error or AIError("upstream", "The AI service is unavailable.")


class AnthropicClient:
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 90.0,
        max_retries: int = 2,
        http_post: HttpPost = _urllib_post,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._api_key = api_key
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._http_post = http_post
        self._sleep = sleep

    def complete_json(
        self,
        *,
        system: str,
        content: list[dict[str, Any]],
        tool_name: str,
        tool_description: str,
        schema: dict[str, Any],
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": content}],
            "tools": [{"name": tool_name, "description": tool_description, "input_schema": schema}],
            "tool_choice": {"type": "tool", "name": tool_name},
        }
        headers = {"content-type": "application/json", "x-api-key": self._api_key, "anthropic-version": ANTHROPIC_VERSION}
        body = post_with_retries(
            self._http_post, f"{self._base_url}/v1/messages", headers, json.dumps(payload).encode("utf-8"),
            timeout=self._timeout, max_retries=self._max_retries, sleep=self._sleep,
        )
        return self._extract_tool_input(body, tool_name)

    @staticmethod
    def _extract_tool_input(body: bytes, tool_name: str) -> dict[str, Any]:
        try:
            data = json.loads(body)
        except (ValueError, TypeError) as error:
            raise AIError("bad_response", "The AI service returned an unreadable response.") from error
        if data.get("stop_reason") == "max_tokens":
            raise AIError("bad_response", "The AI response was cut off before it finished. Please try again with fewer items.")
        for block in data.get("content", []):
            if block.get("type") == "tool_use" and block.get("name") == tool_name and isinstance(block.get("input"), dict):
                return block["input"]
        raise AIError("bad_response", "The AI service did not return a structured answer. Please try again.")


GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
XAI_BASE_URL = "https://api.x.ai/v1"
PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "gemini": {"base_url": GEMINI_BASE_URL, "model": "gemini-flash-latest"},
    "xai": {"base_url": XAI_BASE_URL, "model": "grok-4"},
}


def _to_openai_content(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for block in blocks:
        if block.get("type") == "image":
            src = block["source"]
            out.append({"type": "image_url", "image_url": {"url": f"data:{src['media_type']};base64,{src['data']}"}})
        else:
            out.append({"type": "text", "text": block.get("text", "")})
    return out


def _parse_json_text(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned[4:] if cleaned.lower().startswith("json") else cleaned
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        value = json.loads(cleaned[start:end + 1])
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


class OpenAICompatClient:
    """Chat-completions client for OpenAI-compatible APIs (Google Gemini, xAI Grok).

    Structured output is requested through a forced function call; if the model
    answers with plain JSON text instead, that is accepted as a fallback.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        *,
        timeout: float = 90.0,
        max_retries: int = 2,
        http_post: HttpPost = _urllib_post,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._api_key = api_key
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._http_post = http_post
        self._sleep = sleep

    def complete_json(
        self,
        *,
        system: str,
        content: list[dict[str, Any]],
        tool_name: str,
        tool_description: str,
        schema: dict[str, Any],
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": _to_openai_content(content)},
            ],
            "tools": [{"type": "function", "function": {"name": tool_name, "description": tool_description, "parameters": schema}}],
            "tool_choice": {"type": "function", "function": {"name": tool_name}},
        }
        headers = {"content-type": "application/json", "authorization": f"Bearer {self._api_key}"}
        body = post_with_retries(
            self._http_post, f"{self._base_url}/chat/completions", headers, json.dumps(payload).encode("utf-8"),
            timeout=self._timeout, max_retries=self._max_retries, sleep=self._sleep,
        )
        return self._extract(body, tool_name)

    @staticmethod
    def _extract(body: bytes, tool_name: str) -> dict[str, Any]:
        try:
            data = json.loads(body)
            choice = data["choices"][0]
            message = choice.get("message", {})
        except (ValueError, TypeError, KeyError, IndexError) as error:
            raise AIError("bad_response", "The AI service returned an unreadable response.") from error
        if choice.get("finish_reason") == "length":
            raise AIError("bad_response", "The AI response was cut off before it finished. Please try again with fewer items.")
        for call in message.get("tool_calls") or []:
            function = call.get("function", {})
            if function.get("name") == tool_name:
                try:
                    arguments = json.loads(function.get("arguments") or "")
                except ValueError:
                    break
                if isinstance(arguments, dict):
                    return arguments
        text = message.get("content")
        if isinstance(text, str):
            parsed = _parse_json_text(text)
            if parsed is not None:
                return parsed
        raise AIError("bad_response", "The AI service did not return a structured answer. Please try again.")


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def active_provider() -> str | None:
    """Provider named by FOODVERSE_AI_PROVIDER, else the first one with a key set."""
    keys = {"anthropic": _env("ANTHROPIC_API_KEY"), "gemini": _env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY"), "xai": _env("XAI_API_KEY")}
    chosen = _env("FOODVERSE_AI_PROVIDER").lower()
    if chosen in keys:
        return chosen if keys[chosen] else None
    return next((name for name, key in keys.items() if key), None)


def ai_settings() -> dict[str, Any]:
    provider = active_provider()
    default_model = DEFAULT_MODEL if provider in (None, "anthropic") else PROVIDER_DEFAULTS[provider]["model"]
    return {
        "configured": provider is not None,
        "provider": provider or "none",
        "model": _env("FOODVERSE_AI_MODEL") or default_model,
        "nutritionDatabase": bool(_env("USDA_API_KEY")),
    }


def get_llm() -> LLMClient:
    """Build the configured client or raise ``AIError('not_configured')``."""
    provider = active_provider()
    if provider is None:
        raise AIError(
            "not_configured",
            "AI features are not set up on this server yet. Set ANTHROPIC_API_KEY, GEMINI_API_KEY or XAI_API_KEY to enable them.",
        )
    timeout = float(_env("FOODVERSE_AI_TIMEOUT") or "90")
    if provider == "anthropic":
        return AnthropicClient(
            _env("ANTHROPIC_API_KEY"), _env("FOODVERSE_AI_MODEL") or DEFAULT_MODEL,
            base_url=_env("FOODVERSE_AI_BASE_URL") or DEFAULT_BASE_URL, timeout=timeout,
        )
    defaults = PROVIDER_DEFAULTS[provider]
    key = _env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY") if provider == "gemini" else _env("XAI_API_KEY")
    return OpenAICompatClient(
        key, _env("FOODVERSE_AI_MODEL") or defaults["model"], _env("FOODVERSE_AI_BASE_URL") or defaults["base_url"], timeout=timeout,
    )
