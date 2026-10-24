---
name: Food Verse planner storage
description: Why the app keeps session-scoped meal plans in a separate table.
---

Store each anonymous browser session's weekly plans separately from the legacy date-keyed planner table. Do not replace that table's primary key as a routine schema push.

**Why:** Drizzle flagged changing the existing primary key as a potential data-loss operation. Keeping the old table intact preserves existing rows while allowing separate plans for each session.

**How to apply:** Keep session-scoped plan reads and writes on the additive table. Any future consolidation should include a reviewed, non-destructive migration and preserve existing data.
