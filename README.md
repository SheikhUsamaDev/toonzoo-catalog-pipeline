# ToonZoo Kids — Catalog Pipeline

A weekly-run Python pipeline that discovers new videos from a curated,
manually-vetted YouTube channel allow-list and publishes a JSON manifest
consumed by the ToonZoo Kids mobile app.

## What this does — and does NOT do

**Does:** discover new uploads from allow-listed channels, fetch metadata
(title, thumbnail, duration, safety flags), filter out anything unsuitable,
and publish a versioned JSON manifest.

**Does NOT:** resolve actual playable/downloadable video stream URLs. That
happens client-side, in the mobile app, at download time — resolved stream
URLs expire in ~10 minutes and can't be usefully cached here. This pipeline
only ever stores stable metadata (video IDs, titles, thumbnails), never a
stream URL.

**Does NOT:** use YouTube's open `search.list` endpoint in its normal weekly
run. Only channels explicitly listed in `config/channels.yaml` with
`status: active` are ever pulled from. This is a deliberate child-safety
control — see `config/channels.yaml`'s vetting checklist.

## Setup

```
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Set `YOUTUBE_API_KEY` as an environment variable (get one from Google Cloud
Console → APIs & Services → Credentials, with "YouTube Data API v3" enabled
and the key restricted to that API).

## Adding a new channel

1. Get the channel's ID (starts with `UC`, 24 characters) — from the
   channel's About page → Share channel → Copy channel ID, or run
   `python tools/resolve_handle.py @handle` if you only have the @handle.
2. Add an entry to `config/channels.yaml` under the right category with
   `status: pending`.
3. **Watch at least 5 recent uploads yourself** before ever setting
   `status: active` — see the full vetting checklist at the top of
   `channels.yaml`. This step is not optional and not automatable; it is the
   actual safety mechanism this whole pipeline depends on.

## Running locally

```
python -m catalog_pipeline.run
```

Reads `config/channels.yaml` + `config/settings.yaml`, walks each active
channel's uploads since the last run (tracked in `state/`), applies safety
filters, and writes/updates `manifest/*.json`.

## Running tests

```
pytest
```

## Weekly automation

`.github/workflows/weekly-catalog.yml` runs this every Monday via GitHub
Actions and commits the updated manifest back to the repo. Requires a
`YOUTUBE_API_KEY` repo secret (Settings → Secrets and variables → Actions).
Enable GitHub Pages (Settings → Pages → Deploy from branch → `main` →
`/manifest`) so the mobile app can fetch, e.g.:

```
https://<your-github-username>.github.io/toonzoo-catalog-pipeline/cartoons.json
```

A failed scheduled run emails the repo owner automatically (default GitHub
behavior) — no extra alerting setup needed. Trigger a manual run anytime via
the "Run workflow" button on the Actions tab (`workflow_dispatch`).

## Quota

YouTube Data API v3 free tier: 10,000 units/day. This pipeline avoids
`search.list` (100 units/call) entirely in its normal path, using
`channels.list`/`playlistItems.list`/`videos.list` instead (~1 unit/call,
batched). At ~100 allow-listed channels, a full weekly run costs roughly
120-150 units — comfortable headroom to scale to several thousand channels
before quota becomes a real constraint.
