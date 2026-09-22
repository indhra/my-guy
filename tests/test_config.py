import json

import pytest

from router.config import RouterConfig, SkillRoot, load_config, save_config


def test_config_round_trip_is_private_and_validated(tmp_path):
    path = tmp_path / "config.json"
    expected = RouterConfig(feedback_enabled=True, roots=(SkillRoot("codex", "/skills", "local"),))
    save_config(expected, path)
    assert load_config(path) == expected
    assert path.stat().st_mode & 0o777 == 0o600
    assert json.loads(path.read_text())["schema_version"] == 1


def test_config_rejects_duplicate_or_invalid_roots():
    with pytest.raises(ValueError):
        SkillRoot("../escape", "/tmp")
    with pytest.raises(ValueError):
        RouterConfig(roots=(SkillRoot("same", "/one"), SkillRoot("same", "/two")))
    with pytest.raises(ValueError):
        SkillRoot("relative", "skills")
