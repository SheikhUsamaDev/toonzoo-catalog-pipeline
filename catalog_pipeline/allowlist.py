"""Loads and validates config/channels.yaml — the curated channel allow-list.

This is the primary child-safety control for the whole pipeline: only
channels listed here with status: active are ever pulled from. A malformed
entry should fail the run loudly rather than be silently skipped, since a bad
edit should block publication, not quietly under-populate a category.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

CHANNEL_ID_RE = re.compile(r"^UC[a-zA-Z0-9_-]{22}$")
VALID_STATUSES = {"pending", "active", "disabled"}
VALID_CATEGORIES = {"cartoons", "poems", "naats", "learning", "ayats"}


class AllowlistError(Exception):
    """Raised on a malformed channels.yaml — should abort the run."""


@dataclass
class ChannelEntry:
    channel_id: str
    name: str
    status: str
    category: str
    reels_eligible: bool = False
    max_video_seconds: int | None = None
    notes: str = ""


@dataclass
class Allowlist:
    entries: list[ChannelEntry] = field(default_factory=list)

    def active(self) -> list[ChannelEntry]:
        return [e for e in self.entries if e.status == "active"]

    def by_category(self, category: str) -> list[ChannelEntry]:
        return [e for e in self.active() if e.category == category]


def _validate_entry(raw: dict, category: str, index: int) -> ChannelEntry:
    where = f"channels.yaml categories.{category}[{index}]"

    channel_id = raw.get("channel_id")
    if not isinstance(channel_id, str) or not CHANNEL_ID_RE.match(channel_id):
        raise AllowlistError(
            f"{where}: invalid or missing channel_id {channel_id!r} "
            f"(expected format 'UC' + 22 chars)"
        )

    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise AllowlistError(f"{where}: missing or empty 'name'")

    status = raw.get("status")
    if status not in VALID_STATUSES:
        raise AllowlistError(
            f"{where}: invalid status {status!r}, must be one of {VALID_STATUSES}"
        )

    max_video_seconds = raw.get("max_video_seconds")
    if max_video_seconds is not None and not isinstance(max_video_seconds, int):
        raise AllowlistError(f"{where}: max_video_seconds must be an integer if set")

    return ChannelEntry(
        channel_id=channel_id,
        name=name,
        status=status,
        category=category,
        reels_eligible=bool(raw.get("reels_eligible", False)),
        max_video_seconds=max_video_seconds,
        notes=raw.get("notes", ""),
    )


def load_allowlist(path: str | Path) -> Allowlist:
    path = Path(path)
    if not path.exists():
        raise AllowlistError(f"channels.yaml not found at {path}")

    with path.open("r", encoding="utf-8") as f:
        doc = yaml.safe_load(f)

    if not isinstance(doc, dict) or "categories" not in doc:
        raise AllowlistError("channels.yaml missing top-level 'categories' key")

    categories = doc["categories"]
    entries: list[ChannelEntry] = []
    seen_ids: dict[str, str] = {}

    for category, channel_list in categories.items():
        if category not in VALID_CATEGORIES:
            raise AllowlistError(
                f"channels.yaml: unknown category {category!r}, "
                f"must be one of {VALID_CATEGORIES}"
            )
        if not isinstance(channel_list, list):
            raise AllowlistError(f"channels.yaml categories.{category} must be a list")

        for i, raw in enumerate(channel_list):
            entry = _validate_entry(raw, category, i)
            if entry.channel_id in seen_ids:
                raise AllowlistError(
                    f"channels.yaml: channel_id {entry.channel_id} appears twice "
                    f"(in {seen_ids[entry.channel_id]} and {category})"
                )
            seen_ids[entry.channel_id] = category
            entries.append(entry)

    return Allowlist(entries=entries)
