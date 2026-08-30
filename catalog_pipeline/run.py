"""CLI entrypoint — orchestrates one full weekly-catalog run.

Usage:
    python -m catalog_pipeline.run
"""
import os
import sys
from pathlib import Path

import yaml

from . import discover, manifest as manifest_mod
from .allowlist import load_allowlist, AllowlistError
from .categorize import is_reels_eligible
from .filters import passes_sanity_filters
from .quota import QuotaTracker, QuotaExceededError
from .state import load_json, save_json
from .youtube_client import YouTubeClient, YouTubeApiError

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
MANIFEST_DIR = ROOT / "manifest"
STATE_DIR = ROOT / "state"


def load_settings() -> dict:
    with (CONFIG_DIR / "settings.yaml").open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run() -> int:
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("ERROR: YOUTUBE_API_KEY environment variable is not set.", file=sys.stderr)
        return 1

    try:
        allowlist = load_allowlist(CONFIG_DIR / "channels.yaml")
    except AllowlistError as e:
        print(f"ERROR: channels.yaml is invalid, aborting run: {e}", file=sys.stderr)
        return 1

    settings = load_settings()
    quota = QuotaTracker(max_units_per_run=settings.get("max_units_per_run", 5000))
    client = YouTubeClient(api_key=api_key, quota=quota)

    playlist_cache = load_json(STATE_DIR / "channel_playlists.json")
    cursors = load_json(STATE_DIR / "channel_cursors.json")

    active_channels = allowlist.active()
    if not active_channels:
        print(
            "WARNING: no channels with status: active in channels.yaml — "
            "nothing to do. (Placeholder entries ship as status: pending "
            "on purpose; add real vetted channels before expecting output.)"
        )

    manifest = manifest_mod.load_manifest(MANIFEST_DIR / "manifest.json")

    added_this_run = 0
    rejected_this_run = 0
    channels_processed = 0
    channel_rejection_counts: dict[str, tuple[int, int]] = {}  # id -> (accepted, rejected)

    try:
        discover.resolve_uploads_playlist_ids(client, active_channels, playlist_cache)

        for channel in active_channels:
            uploads_playlist_id = playlist_cache.get(channel.channel_id)
            if not uploads_playlist_id:
                print(
                    f"WARNING: could not resolve uploads playlist for "
                    f"{channel.name} ({channel.channel_id}) — skipping."
                )
                continue

            last_seen = cursors.get(channel.channel_id)
            new_video_ids = discover.discover_new_video_ids(
                client,
                uploads_playlist_id,
                last_seen,
                page_size=settings.get("playlist_page_size", 50),
            )
            channels_processed += 1

            if not new_video_ids:
                continue

            # Advance the cursor to the newest ID seen regardless of whether
            # it later passes filters — this prevents re-fetching (and
            # re-rejecting, burning quota) the same rejected video every week.
            cursors[channel.channel_id] = new_video_ids[0]

            videos = client.get_videos(new_video_ids)

            accepted, rejected = 0, 0
            for video_id in new_video_ids:
                video = videos.get(video_id)
                if not video:
                    rejected += 1
                    continue

                ok, reason = passes_sanity_filters(
                    video, channel.max_video_seconds, settings
                )
                if not ok:
                    rejected += 1
                    rejected_this_run += 1
                    print(f"  rejected {video_id} ({channel.name}): {reason}")
                    continue

                entry = manifest_mod.build_video_entry(
                    video,
                    channel_id=channel.channel_id,
                    channel_title=channel.name,
                    reels_eligible=is_reels_eligible(video, channel, settings),
                )

                added = manifest_mod.append_videos(manifest, channel.category, [entry])
                if added and entry["reels_eligible"]:
                    manifest_mod.append_videos(manifest, "reels", [entry])
                added_this_run += added
                accepted += 1

            channel_rejection_counts[channel.name] = (accepted, rejected)

    except QuotaExceededError as e:
        print(f"WARNING: {e}")
        print("Publishing whatever was collected before the budget was hit.")
    except YouTubeApiError as e:
        print(f"ERROR: YouTube API call failed: {e}", file=sys.stderr)
        # Still fall through to save cursors/manifest for whatever succeeded
        # before the failure, rather than losing partial progress.

    manifest_mod.finalize_stats(manifest, added_this_run, rejected_this_run, channels_processed)
    manifest_mod.write_manifest(manifest, MANIFEST_DIR)
    save_json(STATE_DIR / "channel_playlists.json", playlist_cache)
    save_json(STATE_DIR / "channel_cursors.json", cursors)

    print()
    print(f"Channels processed: {channels_processed}")
    print(f"Videos added: {added_this_run}")
    print(f"Videos rejected: {rejected_this_run}")
    for name, (accepted, rejected) in channel_rejection_counts.items():
        total = accepted + rejected
        if total >= 5 and rejected / total > 0.5:
            print(
                f"WARNING: channel {name!r} had {rejected}/{total} uploads "
                f"rejected this run — review its allow-list status."
            )
    print()
    print(quota.summary())

    return 0


if __name__ == "__main__":
    sys.exit(run())
