"""Per-video sanity filtering — a secondary safety net on top of the channel
allow-list (the primary control). Every rejection should be logged with a
reason so a channel that's started drifting can be caught (see run.py's
per-channel rejection-rate warning).
"""
import re

_ISO8601_DURATION_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def parse_iso8601_duration(duration: str) -> int:
    match = _ISO8601_DURATION_RE.match(duration or "")
    if not match:
        return 0
    h, m, s = (int(g) if g else 0 for g in match.groups())
    return h * 3600 + m * 60 + s


def passes_sanity_filters(
    video: dict, channel_max_video_seconds: int | None, settings: dict
) -> tuple[bool, str]:
    status = video.get("status", {})
    content = video.get("contentDetails", {})
    snippet = video.get("snippet", {})

    if status.get("privacyStatus") != "public":
        return False, "not public"
    if status.get("uploadStatus") != "processed":
        return False, "not fully processed"
    if status.get("embeddable") is False:
        return False, "not embeddable"

    # Only reject an EXPLICIT False. Missing/None is "unknown" and allowed
    # through (many legitimate channels don't declare this), but an explicit
    # False is a strong signal this video doesn't belong in a kids app.
    if status.get("madeForKids") is False:
        return False, "explicitly marked not made for kids"

    if content.get("contentRating", {}).get("ytRating") == "ytAgeRestricted":
        return False, "age restricted"

    duration = parse_iso8601_duration(content.get("duration", ""))
    if duration <= 0:
        return False, "invalid/zero duration"

    max_seconds = channel_max_video_seconds or settings.get("max_video_seconds", 3600)
    if duration > max_seconds:
        return False, f"exceeds max duration cap ({max_seconds}s)"

    thumbs = snippet.get("thumbnails", {})
    if not (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default")):
        return False, "no usable thumbnail"

    if not snippet.get("title", "").strip():
        return False, "empty title"

    text = f"{snippet.get('title', '')} {snippet.get('description', '')}".lower()
    blocklist = settings.get("title_description_blocklist", [])
    for term in blocklist:
        if term.lower() in text:
            return False, f"matched blocklist term: {term!r}"

    return True, "ok"
