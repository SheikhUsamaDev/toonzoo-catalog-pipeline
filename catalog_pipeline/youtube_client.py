"""Thin wrapper over the YouTube Data API v3 endpoints this pipeline needs.

Deliberately uses only channels.list / playlistItems.list / videos.list —
NEVER search.list — to keep quota cost near-flat as the catalog grows. See
README.md for the reasoning and cost comparison.
"""
import time
from typing import Iterator

import requests

from .quota import QuotaTracker

API_BASE = "https://www.googleapis.com/youtube/v3"

# Actual YouTube Data API v3 unit costs for the calls this pipeline makes.
COST_CHANNELS_LIST = 1
COST_PLAYLIST_ITEMS_LIST = 1
COST_VIDEOS_LIST = 1

_MAX_RETRIES = 3
_RETRY_BACKOFF_SECONDS = 2


class YouTubeApiError(Exception):
    pass


class YouTubeClient:
    def __init__(self, api_key: str, quota: QuotaTracker):
        self.api_key = api_key
        self.quota = quota
        self._session = requests.Session()

    def _get(self, endpoint: str, params: dict) -> dict:
        params = {**params, "key": self.api_key}
        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                resp = self._session.get(
                    f"{API_BASE}/{endpoint}", params=params, timeout=20
                )
                if resp.status_code == 403:
                    body = resp.text[:500]
                    raise YouTubeApiError(
                        f"{endpoint} returned 403 (quota exceeded or key invalid): {body}"
                    )
                resp.raise_for_status()
                return resp.json()
            except (requests.RequestException, YouTubeApiError) as e:
                last_error = e
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_RETRY_BACKOFF_SECONDS * (attempt + 1))
        raise YouTubeApiError(f"{endpoint} failed after {_MAX_RETRIES} attempts: {last_error}")

    def get_channels(self, channel_ids: list[str]) -> dict[str, dict]:
        """Batched channels.list — up to 50 IDs per call, 1 unit total per call."""
        result: dict[str, dict] = {}
        for i in range(0, len(channel_ids), 50):
            batch = channel_ids[i : i + 50]
            data = self._get(
                "channels",
                {"part": "contentDetails,status,snippet", "id": ",".join(batch)},
            )
            self.quota.charge("channels.list", COST_CHANNELS_LIST)
            for item in data.get("items", []):
                result[item["id"]] = item
        return result

    def iter_playlist_items(
        self, playlist_id: str, page_size: int = 50
    ) -> Iterator[dict]:
        """Yields playlistItems in reverse-chronological order (newest first),
        paginating forward. Caller is responsible for stopping early once a
        known video ID (from the cursor) is reached — this generator will
        walk the whole playlist if allowed to, which the caller should not do
        for a routine weekly run.
        """
        page_token = None
        while True:
            params = {
                "part": "snippet,contentDetails",
                "playlistId": playlist_id,
                "maxResults": page_size,
            }
            if page_token:
                params["pageToken"] = page_token
            data = self._get("playlistItems", params)
            self.quota.charge("playlistItems.list", COST_PLAYLIST_ITEMS_LIST)

            for item in data.get("items", []):
                yield item

            page_token = data.get("nextPageToken")
            if not page_token:
                return

    def get_videos(self, video_ids: list[str]) -> dict[str, dict]:
        """Batched videos.list — up to 50 IDs per call, 1 unit total per call."""
        result: dict[str, dict] = {}
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i : i + 50]
            data = self._get(
                "videos",
                {
                    "part": "snippet,contentDetails,status,statistics",
                    "id": ",".join(batch),
                },
            )
            self.quota.charge("videos.list", COST_VIDEOS_LIST)
            for item in data.get("items", []):
                result[item["id"]] = item
        return result
