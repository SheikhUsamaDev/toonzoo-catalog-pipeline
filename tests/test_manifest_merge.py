import json

from catalog_pipeline import manifest as manifest_mod


def make_entry(video_id: str, title: str = "Some Video") -> dict:
    return {
        "video_id": video_id,
        "title": title,
        "channel_id": "UCabc",
        "channel_title": "Test Channel",
        "published_at": "2026-01-01T00:00:00Z",
        "duration_seconds": 300,
        "thumbnail_url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        "tags": [],
        "reels_eligible": False,
        "added_at": "2026-01-01T00:00:00Z",
        "source": "youtube",
    }


def test_empty_manifest_has_all_categories():
    m = manifest_mod.empty_manifest()
    for cat in manifest_mod.CATEGORIES:
        assert m["categories"][cat]["videos"] == []


def test_append_videos_adds_new_entries():
    m = manifest_mod.empty_manifest()
    added = manifest_mod.append_videos(m, "cartoons", [make_entry("v1"), make_entry("v2")])
    assert added == 2
    assert len(m["categories"]["cartoons"]["videos"]) == 2


def test_append_videos_dedupes_existing():
    m = manifest_mod.empty_manifest()
    manifest_mod.append_videos(m, "cartoons", [make_entry("v1")])
    added = manifest_mod.append_videos(m, "cartoons", [make_entry("v1"), make_entry("v2")])
    # only v2 should count as newly added; v1 already existed
    assert added == 1
    assert len(m["categories"]["cartoons"]["videos"]) == 2


def test_append_videos_never_overwrites_existing_fields():
    m = manifest_mod.empty_manifest()
    manifest_mod.append_videos(m, "cartoons", [make_entry("v1", title="Original Title")])
    manifest_mod.append_videos(m, "cartoons", [make_entry("v1", title="Changed Title")])
    titles = [v["title"] for v in m["categories"]["cartoons"]["videos"]]
    assert titles == ["Original Title"]


def test_load_manifest_returns_empty_when_missing(tmp_path):
    m = manifest_mod.load_manifest(tmp_path / "does_not_exist.json")
    assert m["stats"]["total_videos"] == 0


def test_write_and_load_roundtrip(tmp_path):
    m = manifest_mod.empty_manifest()
    manifest_mod.append_videos(m, "poems", [make_entry("p1")])
    manifest_mod.finalize_stats(m, added_this_run=1, rejected_this_run=0, channels_processed=1)
    manifest_mod.write_manifest(m, tmp_path)

    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "poems.json").exists()
    assert (tmp_path / "cartoons.json").exists()

    reloaded = manifest_mod.load_manifest(tmp_path / "manifest.json")
    assert len(reloaded["categories"]["poems"]["videos"]) == 1
    assert reloaded["categories"]["poems"]["videos"][0]["video_id"] == "p1"

    with (tmp_path / "poems.json").open() as f:
        split = json.load(f)
    assert split["videos"][0]["video_id"] == "p1"


def test_load_manifest_rejects_schema_mismatch(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"schema_version": 999, "categories": {}}))
    try:
        manifest_mod.load_manifest(path)
        assert False, "expected ValueError for schema mismatch"
    except ValueError:
        pass
