import pytest

from catalog_pipeline.allowlist import load_allowlist, AllowlistError

VALID_ID = "UCbCmjCuTUZos6Inko4u57UQ"


def write_yaml(tmp_path, content: str):
    path = tmp_path / "channels.yaml"
    path.write_text(content)
    return path


def test_loads_valid_config(tmp_path):
    path = write_yaml(
        tmp_path,
        f"""
categories:
  cartoons:
    - channel_id: "{VALID_ID}"
      name: "Test Channel"
      status: active
      reels_eligible: true
""",
    )
    allowlist = load_allowlist(path)
    assert len(allowlist.entries) == 1
    assert allowlist.active()[0].channel_id == VALID_ID


def test_pending_channels_excluded_from_active(tmp_path):
    path = write_yaml(
        tmp_path,
        f"""
categories:
  cartoons:
    - channel_id: "{VALID_ID}"
      name: "Test Channel"
      status: pending
""",
    )
    allowlist = load_allowlist(path)
    assert allowlist.active() == []


def test_rejects_invalid_channel_id(tmp_path):
    path = write_yaml(
        tmp_path,
        """
categories:
  cartoons:
    - channel_id: "not-a-real-id"
      name: "Bad Channel"
      status: active
""",
    )
    with pytest.raises(AllowlistError, match="invalid or missing channel_id"):
        load_allowlist(path)


def test_rejects_invalid_status(tmp_path):
    path = write_yaml(
        tmp_path,
        f"""
categories:
  cartoons:
    - channel_id: "{VALID_ID}"
      name: "Test Channel"
      status: not_a_real_status
""",
    )
    with pytest.raises(AllowlistError, match="invalid status"):
        load_allowlist(path)


def test_rejects_unknown_category(tmp_path):
    path = write_yaml(
        tmp_path,
        f"""
categories:
  not_a_real_category:
    - channel_id: "{VALID_ID}"
      name: "Test Channel"
      status: active
""",
    )
    with pytest.raises(AllowlistError, match="unknown category"):
        load_allowlist(path)


def test_rejects_duplicate_channel_id(tmp_path):
    path = write_yaml(
        tmp_path,
        f"""
categories:
  cartoons:
    - channel_id: "{VALID_ID}"
      name: "Channel A"
      status: active
  poems:
    - channel_id: "{VALID_ID}"
      name: "Channel B"
      status: active
""",
    )
    with pytest.raises(AllowlistError, match="appears twice"):
        load_allowlist(path)


def test_missing_file_raises(tmp_path):
    with pytest.raises(AllowlistError, match="not found"):
        load_allowlist(tmp_path / "does_not_exist.yaml")
