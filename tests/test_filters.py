from catalog_pipeline.filters import parse_iso8601_duration, passes_sanity_filters

SETTINGS = {
    "max_video_seconds": 3600,
    "title_description_blocklist": ["onlyfans", "18+"],
}


def make_video(**overrides) -> dict:
    base = {
        "status": {
            "privacyStatus": "public",
            "uploadStatus": "processed",
            "embeddable": True,
            "madeForKids": True,
        },
        "contentDetails": {
            "duration": "PT5M30S",
            "contentRating": {},
        },
        "snippet": {
            "title": "Fun Cartoon Episode",
            "description": "A fun episode for kids",
            "thumbnails": {"high": {"url": "https://example.com/hq.jpg"}},
        },
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and key in base:
            base[key] = {**base[key], **value}
        else:
            base[key] = value
    return base


def test_parse_duration():
    assert parse_iso8601_duration("PT5M30S") == 330
    assert parse_iso8601_duration("PT1H") == 3600
    assert parse_iso8601_duration("PT45S") == 45
    assert parse_iso8601_duration("") == 0
    assert parse_iso8601_duration("garbage") == 0


def test_accepts_valid_video():
    ok, reason = passes_sanity_filters(make_video(), None, SETTINGS)
    assert ok is True
    assert reason == "ok"


def test_rejects_non_public():
    video = make_video(status={"privacyStatus": "private"})
    ok, reason = passes_sanity_filters(video, None, SETTINGS)
    assert ok is False
    assert "not public" in reason


def test_rejects_explicit_not_made_for_kids():
    video = make_video(status={"madeForKids": False})
    ok, reason = passes_sanity_filters(video, None, SETTINGS)
    assert ok is False
    assert "not made for kids" in reason


def test_allows_unknown_made_for_kids():
    video = make_video(status={"madeForKids": None})
    ok, _ = passes_sanity_filters(video, None, SETTINGS)
    assert ok is True


def test_rejects_age_restricted():
    video = make_video(contentDetails={"contentRating": {"ytRating": "ytAgeRestricted"}})
    ok, reason = passes_sanity_filters(video, None, SETTINGS)
    assert ok is False
    assert "age restricted" in reason


def test_rejects_zero_duration():
    video = make_video(contentDetails={"duration": "PT0S"})
    ok, reason = passes_sanity_filters(video, None, SETTINGS)
    assert ok is False
    assert "duration" in reason


def test_rejects_over_duration_cap():
    video = make_video(contentDetails={"duration": "PT2H"})
    ok, reason = passes_sanity_filters(video, None, SETTINGS)
    assert ok is False
    assert "exceeds max duration cap" in reason


def test_channel_override_duration_cap():
    video = make_video(contentDetails={"duration": "PT20M"})
    ok, reason = passes_sanity_filters(video, channel_max_video_seconds=600, settings=SETTINGS)
    assert ok is False
    assert "600s" in reason


def test_rejects_missing_thumbnail():
    video = make_video(snippet={"thumbnails": {}})
    ok, reason = passes_sanity_filters(video, None, SETTINGS)
    assert ok is False
    assert "thumbnail" in reason


def test_rejects_empty_title():
    video = make_video(snippet={"title": "   "})
    ok, reason = passes_sanity_filters(video, None, SETTINGS)
    assert ok is False
    assert "empty title" in reason


def test_rejects_blocklisted_term():
    video = make_video(snippet={"title": "Check out my ONLYFANS"})
    ok, reason = passes_sanity_filters(video, None, SETTINGS)
    assert ok is False
    assert "blocklist" in reason
