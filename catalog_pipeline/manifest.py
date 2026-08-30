"""Manifest load/merge/write. Append-only by design: an existing entry's
fields are never overwritten on a routine run, which avoids diff noise and
preserves added_at history. Writes are atomic (write to .tmp, then rename)
so a crash mid-write can never leave a half-written manifest published.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
CATEGORIES = ("cartoons", "poems", "naats", "reels")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def empty_manifest() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "categories": {cat: {"videos": []} for cat in CATEGORIES},
        "stats": {
            "total_videos": 0,
            "added_this_run": 0,
            "rejected_this_run": 0,
            "channels_processed": 0,
        },
    }


def load_manifest(path: str | Path) -> dict:
    path = Path(path)
    if not path.exists():
        return empty_manifest()
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"manifest.json schema_version {data.get('schema_version')!r} "
            f"does not match expected {SCHEMA_VERSION} — needs a migration, "
            f"not a routine merge."
        )
    for cat in CATEGORIES:
        data["categories"].setdefault(cat, {"videos": []})
    return data


def build_video_entry(
    video: dict, channel_id: str, channel_title: str, reels_eligible: bool
) -> dict:
    snippet = video.get("snippet", {})
    content = video.get("contentDetails", {})
    from .filters import parse_iso8601_duration

    video_id = video["id"]
    thumbs = snippet.get("thumbnails", {})
    thumb = thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}

    return {
        "video_id": video_id,
        "title": snippet.get("title", ""),
        "channel_id": channel_id,
        "channel_title": channel_title,
        "published_at": snippet.get("publishedAt"),
        "duration_seconds": parse_iso8601_duration(content.get("duration", "")),
        "thumbnail_url": thumb.get("url")
        or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        "tags": snippet.get("tags", [])[:20],
        "reels_eligible": reels_eligible,
        "added_at": _now_iso(),
        "source": "youtube",
    }


def existing_video_ids(manifest: dict, category: str) -> set[str]:
    return {v["video_id"] for v in manifest["categories"][category]["videos"]}


def append_videos(manifest: dict, category: str, new_entries: list[dict]) -> int:
    """Appends only entries whose video_id isn't already present. Returns the
    count actually added."""
    existing = existing_video_ids(manifest, category)
    added = 0
    for entry in new_entries:
        if entry["video_id"] in existing:
            continue
        manifest["categories"][category]["videos"].append(entry)
        existing.add(entry["video_id"])
        added += 1
    return added


def finalize_stats(manifest: dict, added_this_run: int, rejected_this_run: int, channels_processed: int) -> None:
    manifest["generated_at"] = _now_iso()
    total = sum(len(manifest["categories"][c]["videos"]) for c in CATEGORIES)
    manifest["stats"] = {
        "total_videos": total,
        "added_this_run": added_this_run,
        "rejected_this_run": rejected_this_run,
        "channels_processed": channels_processed,
    }


def _atomic_write_json(path: Path, data: dict) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp_path, path)


def write_manifest(manifest: dict, manifest_dir: str | Path) -> None:
    manifest_dir = Path(manifest_dir)
    manifest_dir.mkdir(parents=True, exist_ok=True)

    _atomic_write_json(manifest_dir / "manifest.json", manifest)

    for cat in CATEGORIES:
        split = {
            "schema_version": manifest["schema_version"],
            "generated_at": manifest["generated_at"],
            "videos": manifest["categories"][cat]["videos"],
        }
        _atomic_write_json(manifest_dir / f"{cat}.json", split)
