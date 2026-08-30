"""Category assignment and Reels-pool eligibility.

Category is inherited directly from which channels.yaml list a channel
belongs to — never inferred from title/tags/ML. Reels eligibility is a
derived pool (not a separate channel list): any video from a
reels_eligible channel under the duration cap qualifies, so a video can
appear in both its primary category and the Reels pool.
"""
from .allowlist import ChannelEntry
from .filters import parse_iso8601_duration


def is_reels_eligible(video: dict, channel: ChannelEntry, settings: dict) -> bool:
    if not channel.reels_eligible:
        return False
    duration = parse_iso8601_duration(video.get("contentDetails", {}).get("duration", ""))
    return duration <= settings.get("reels_max_seconds", 90)
