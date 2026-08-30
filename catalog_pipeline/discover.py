"""Per-channel uploads-playlist discovery, stopping at a cursor so quota cost
stays flat as the catalog grows (never walks a channel's full history on a
routine run).
"""
from .allowlist import ChannelEntry
from .youtube_client import YouTubeClient


def resolve_uploads_playlist_ids(
    client: YouTubeClient,
    channels: list[ChannelEntry],
    playlist_cache: dict[str, str],
) -> dict[str, str]:
    """Returns channel_id -> uploads_playlist_id, only calling channels.list
    for channel_ids not already present in playlist_cache."""
    missing = [c.channel_id for c in channels if c.channel_id not in playlist_cache]
    if missing:
        details = client.get_channels(missing)
        for channel_id, data in details.items():
            uploads_id = (
                data.get("contentDetails", {})
                .get("relatedPlaylists", {})
                .get("uploads")
            )
            if uploads_id:
                playlist_cache[channel_id] = uploads_id
    return playlist_cache


def discover_new_video_ids(
    client: YouTubeClient,
    uploads_playlist_id: str,
    last_seen_video_id: str | None,
    page_size: int = 50,
    max_pages: int = 20,
) -> list[str]:
    """Walks the uploads playlist newest-first, collecting video IDs until
    last_seen_video_id is reached (exclusive) or the playlist is exhausted.
    Returns IDs in newest-first order; caller should reverse before writing
    to the manifest if oldest-first insertion order is preferred there.

    max_pages bounds cost when last_seen_video_id is None (first-ever run for
    a channel) or its cursor was lost/removed — without this, a channel with
    thousands of back-catalog uploads would walk its ENTIRE history on a
    single run. 20 pages * 50 items = up to 1000 videos, which is already a
    generous first-run backfill; a channel needing more than that gets picked
    up incrementally over subsequent weekly runs instead.
    """
    new_ids: list[str] = []
    for page_num, item in enumerate(
        client.iter_playlist_items(uploads_playlist_id, page_size=page_size)
    ):
        if page_num >= max_pages * page_size:
            break
        video_id = item.get("contentDetails", {}).get("videoId")
        if not video_id:
            continue
        if last_seen_video_id is not None and video_id == last_seen_video_id:
            break
        new_ids.append(video_id)
    return new_ids
