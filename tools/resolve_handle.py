"""Resolve a YouTube @handle to its channel ID, for filling in channels.yaml.

Usage:
    python tools/resolve_handle.py @somechannel
"""
import os
import sys

import requests

API_BASE = "https://www.googleapis.com/youtube/v3"


def resolve_handle(handle: str, api_key: str) -> str | None:
    handle = handle.lstrip("@")
    resp = requests.get(
        f"{API_BASE}/channels",
        params={"part": "id,snippet", "forHandle": handle, "key": api_key},
        timeout=15,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        return None
    return items[0]["id"]


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python tools/resolve_handle.py @somechannel")
        sys.exit(1)

    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("Set YOUTUBE_API_KEY in your environment first.")
        sys.exit(1)

    channel_id = resolve_handle(sys.argv[1], api_key)
    if channel_id is None:
        print(f"No channel found for handle {sys.argv[1]!r}")
        sys.exit(1)

    print(channel_id)


if __name__ == "__main__":
    main()
