"""Validation of browser-supplied images / video frames before they reach a model."""
from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass
from typing import Any

from .llm import AIError

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_TOTAL_BYTES = 24 * 1024 * 1024
MAX_IMAGES = 4
MAX_VIDEO_FRAMES = 8
ALLOWED_TYPES = ("image/jpeg", "image/png", "image/webp", "image/gif")

_DATA_URL = re.compile(r"^data:([\w.+-]+/[\w.+-]+);base64,", re.IGNORECASE)


@dataclass(frozen=True)
class MediaItem:
    media_type: str
    data: str  # base64, no prefix
    size: int
    timestamp: float | None = None


def _sniff(raw: bytes) -> str | None:
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    if raw[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return None


def parse_images(items: list[dict[str, Any]] | None, *, max_items: int = MAX_IMAGES, label: str = "image") -> list[MediaItem]:
    if not items:
        raise AIError("invalid_input", f"Add at least one {label} to analyze.")
    if len(items) > max_items:
        raise AIError("invalid_input", f"Too many {label}s: the limit is {max_items}.")
    parsed: list[MediaItem] = []
    total = 0
    for index, item in enumerate(items, start=1):
        raw_text = str(item.get("data") or "").strip()
        declared = str(item.get("mimeType") or "").lower()
        match = _DATA_URL.match(raw_text)
        if match:
            declared = declared or match.group(1).lower()
            raw_text = raw_text[match.end():]
        try:
            raw = base64.b64decode(raw_text, validate=True)
        except (binascii.Error, ValueError) as error:
            raise AIError("invalid_input", f"The {label} #{index} could not be read. Please choose a different file.") from error
        if not raw:
            raise AIError("invalid_input", f"The {label} #{index} is empty.")
        if len(raw) > MAX_IMAGE_BYTES:
            raise AIError("invalid_input", f"The {label} #{index} is larger than 5 MB. Try a smaller photo.")
        sniffed = _sniff(raw)
        if sniffed is None or sniffed not in ALLOWED_TYPES:
            raise AIError("invalid_input", f"The {label} #{index} is not a supported format. Use JPG, PNG, WEBP or GIF.")
        total += len(raw)
        if total > MAX_TOTAL_BYTES:
            raise AIError("invalid_input", "The combined upload is too large. Try fewer or smaller files.")
        timestamp = item.get("timestamp")
        parsed.append(
            MediaItem(
                sniffed,
                base64.b64encode(raw).decode("ascii"),
                len(raw),
                float(timestamp) if isinstance(timestamp, (int, float)) and timestamp >= 0 else None,
            )
        )
    return parsed


def image_blocks(items: list[MediaItem], *, caption_prefix: str = "Image") -> list[dict[str, Any]]:
    """Content blocks, each image preceded by a short caption so the model can cite it."""
    blocks: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        caption = f"{caption_prefix} {index} of {len(items)}"
        if item.timestamp is not None:
            caption += f" (video time {item.timestamp:.1f}s)"
        blocks.append({"type": "text", "text": caption + ":"})
        blocks.append({"type": "image", "source": {"type": "base64", "media_type": item.media_type, "data": item.data}})
    return blocks
