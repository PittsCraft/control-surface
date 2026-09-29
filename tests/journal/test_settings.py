"""`surface.json`: defaults, effective values, and the refusals."""

import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from surface_status.settings import (
    Models,
    Settings,
    SettingsError,
    load_settings,
    parse_settings,
    settings_path,
)


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "surface.json"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_defaults_are_those_of_specs_section_11() -> None:
    settings = Settings()
    assert settings.plans_dir == "docs/plans"
    assert settings.max_autonomous_passes == 3
    assert settings.models == Models(
        extractor="opus", checker="opus", executor="sonnet", reviewer="opus"
    )


def test_a_missing_file_gives_the_defaults(tmp_path: Path) -> None:
    assert load_settings(settings_path(tmp_path)) == Settings()
    assert settings_path(tmp_path) == tmp_path / ".claude" / "surface.json"


def test_every_key_is_read(tmp_path: Path) -> None:
    text = json.dumps(
        {
            "plans_dir": "plans/",
            "max_autonomous_passes": 5,
            "models": {"executor": "opus"},
        }
    )
    assert load_settings(_write(tmp_path, text)) == Settings(
        plans_dir="plans", max_autonomous_passes=5, models=Models(executor="opus")
    )


def test_the_other_models_keep_their_default_when_one_is_set() -> None:
    assert parse_settings({"models": {"reviewer": "sonnet"}}).models == Models(reviewer="sonnet")


def test_the_effective_settings_print_in_the_shape_of_the_file() -> None:
    effective = Settings().to_dict()
    assert effective["models"] == {
        "extractor": "opus",
        "checker": "opus",
        "executor": "sonnet",
        "reviewer": "opus",
    }
    assert parse_settings(effective) == Settings()


@given(
    st.sampled_from(["docs/plans", "plans", "a/b/c"]),
    st.integers(1, 50),
    st.sampled_from(["opus", "sonnet", "haiku"]),
)
def test_the_effective_settings_always_read_back_as_themselves(
    plans_dir: str, passes: int, executor: str
) -> None:
    settings = Settings(plans_dir, passes, Models(executor=executor))
    assert parse_settings(json.loads(json.dumps(settings.to_dict()))) == settings


def test_an_unknown_key_is_refused_with_the_closest_known_one() -> None:
    with pytest.raises(
        SettingsError, match=r"unknown setting 'plan_dir' \(did you mean 'plans_dir'"
    ):
        parse_settings({"plan_dir": "plans"})
    with pytest.raises(SettingsError, match="known: plans_dir, max_autonomous_passes"):
        parse_settings({"zzz": 1})


@pytest.mark.parametrize(
    ("key", "replacement"),
    [
        ("gate_command", "the gates are the commands the approved plan names"),
        ("gate_timeout_minutes", "a fixed timeout of 30 minutes"),
        ("mark_pr_ready", "the developer marks the pull request ready"),
    ],
)
def test_a_removed_key_is_refused_with_what_replaced_it(
    tmp_path: Path, key: str, replacement: str
) -> None:
    path = _write(tmp_path, json.dumps({"max_autonomous_passes": 2, key: None}))
    with pytest.raises(SettingsError) as error:
        load_settings(path)
    message = str(error.value)
    assert message.startswith(f"{path}: the setting {key!r} is gone: ")
    assert replacement in message
    assert message.endswith("; remove the key")


def test_an_unknown_model_role_is_refused() -> None:
    with pytest.raises(
        SettingsError, match=r"unknown model role 'reviwer' \(did you mean 'reviewer'"
    ):
        parse_settings({"models": {"reviwer": "opus"}})


@pytest.mark.parametrize(
    ("raw", "fragment"),
    [
        ({"plans_dir": ""}, "plans_dir"),
        ({"plans_dir": "/abs"}, "inside the project"),
        ({"plans_dir": "../out"}, "inside the project"),
        ({"plans_dir": "a/../../out"}, "inside the project"),
        ({"plans_dir": "a\\b"}, "inside the project"),
        ({"plans_dir": "."}, "inside the project"),
        ({"plans_dir": 3}, "plans_dir"),
        ({"max_autonomous_passes": 0}, "at least 1"),
        ({"max_autonomous_passes": True}, "max_autonomous_passes"),
        ({"max_autonomous_passes": 2.5}, "max_autonomous_passes"),
        ({"max_autonomous_passes": "3"}, "max_autonomous_passes"),
        ({"models": []}, "models must be an object"),
        ({"models": {"executor": ""}}, "models.executor"),
        ({"models": {"executor": None}}, "models.executor"),
    ],
)
def test_a_wrong_value_is_refused_and_named(raw: dict[str, object], fragment: str) -> None:
    with pytest.raises(SettingsError, match=fragment):
        parse_settings(raw)


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("", "not valid JSON"),
        ("[]", "expected a JSON object"),
        ('{"plans_dir": "a", "plans_dir": "b"}', "duplicate key"),
        ('{"max_autonomous_passes": NaN}', "NaN"),
        ('{"plans_dir": 3}', "plans_dir"),
    ],
)
def test_a_bad_file_is_refused_with_its_path(tmp_path: Path, text: str, fragment: str) -> None:
    path = _write(tmp_path, text)
    with pytest.raises(SettingsError, match=fragment) as error:
        load_settings(path)
    assert str(path) in str(error.value)


def test_a_file_that_is_not_utf8_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "surface.json"
    path.write_bytes(b"\xff")
    with pytest.raises(SettingsError, match="cannot be read"):
        load_settings(path)


def test_reading_the_settings_never_writes_them(tmp_path: Path) -> None:
    path = _write(tmp_path, '{"plans_dir":   "plans"}')
    before = path.read_bytes()
    load_settings(path)
    assert path.read_bytes() == before
