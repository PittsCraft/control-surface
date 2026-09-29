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

TEMPLATE = Path(__file__).resolve().parents[2] / "templates" / "surface.json"


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "surface.json"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_defaults_are_those_of_specs_section_11() -> None:
    settings = Settings()
    assert settings.plans_dir == "docs/plans"
    assert settings.max_autonomous_passes == 3
    assert settings.gate_command is None
    assert settings.gate_timeout_minutes == 30
    assert settings.models == Models(
        extractor="opus", checker="opus", executor="sonnet", reviewer="opus"
    )
    assert settings.mark_pr_ready is False


def test_the_file_installed_in_a_host_gives_the_defaults() -> None:
    assert load_settings(TEMPLATE) == Settings()


def test_a_missing_file_gives_the_defaults(tmp_path: Path) -> None:
    assert load_settings(settings_path(tmp_path)) == Settings()
    assert settings_path(tmp_path) == tmp_path / ".claude" / "surface.json"


def test_every_key_is_read(tmp_path: Path) -> None:
    text = json.dumps(
        {
            "plans_dir": "plans/",
            "max_autonomous_passes": 5,
            "gate_command": "make check",
            "gate_timeout_minutes": 10,
            "models": {"executor": "opus"},
            "mark_pr_ready": True,
        }
    )
    assert load_settings(_write(tmp_path, text)) == Settings(
        plans_dir="plans",
        max_autonomous_passes=5,
        gate_command="make check",
        gate_timeout_minutes=10,
        models=Models(executor="opus"),
        mark_pr_ready=True,
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
    st.none() | st.sampled_from(["make check", "./gate.sh"]),
    st.integers(1, 600),
    st.booleans(),
)
def test_the_effective_settings_always_read_back_as_themselves(
    plans_dir: str,
    passes: int,
    command: str | None,
    timeout: int,
    ready: bool,  # noqa: FBT001 (hypothesis passes arguments by position)
) -> None:
    settings = Settings(plans_dir, passes, command, timeout, Models(), ready)
    assert parse_settings(json.loads(json.dumps(settings.to_dict()))) == settings


def test_an_unknown_key_is_refused_with_the_closest_known_one() -> None:
    with pytest.raises(
        SettingsError, match=r"unknown setting 'gate_cmd' \(did you mean 'gate_command'"
    ):
        parse_settings({"gate_cmd": "make"})
    with pytest.raises(SettingsError, match="known: plans_dir, max_autonomous_passes"):
        parse_settings({"zzz": 1})


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
        ({"gate_command": ""}, "gate_command"),
        ({"gate_command": " make"}, "gate_command"),
        ({"gate_command": ["make"]}, "gate_command"),
        ({"gate_timeout_minutes": -1}, "gate_timeout_minutes"),
        ({"models": []}, "models must be an object"),
        ({"models": {"executor": ""}}, "models.executor"),
        ({"models": {"executor": None}}, "models.executor"),
        ({"mark_pr_ready": "yes"}, "mark_pr_ready"),
        ({"mark_pr_ready": 1}, "mark_pr_ready"),
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
        ('{"gate_command": null, "gate_command": "x"}', "duplicate key"),
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
    path = _write(tmp_path, '{"gate_command":   "make"}')
    before = path.read_bytes()
    load_settings(path)
    assert path.read_bytes() == before
