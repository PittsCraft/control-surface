"""`.claude/surface.json`: the per-project settings, with their defaults.

The file is optional, and so is every key: the chain runs without it (ADR 0019). An unknown key is
refused with a message that names the closest known one, since a misspelled setting silently
ignored would be a setting lost. A key the chain no longer reads is refused with a message that
names what replaced it. The file belongs to the host project: this module reads it and never
writes it.
"""

import difflib
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from pathlib import Path, PurePosixPath
from typing import cast

from surface_status.strict_json import JsonError, loads_object

SETTINGS_FILE = Path(".claude") / "surface.json"

# Keys of earlier versions, and what took their place (ADR 0034).
REMOVED_KEYS: Mapping[str, str] = {
    "gate_command": (
        "the gates are the commands the approved plan names in the gates block of its plan.md,"
        " which /surface-plan finds in the project"
    ),
    "gate_timeout_minutes": "a gate run has a fixed timeout of 30 minutes",
    "mark_pr_ready": "the developer marks the pull request ready, when they want, once conform",
}


class SettingsError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Models:
    """The model alias passed at launch to each agent role."""

    extractor: str = "opus"
    checker: str = "opus"
    executor: str = "sonnet"
    reviewer: str = "opus"


@dataclass(frozen=True, slots=True)
class Settings:
    plans_dir: str = "docs/plans"
    max_autonomous_passes: int = 3
    models: Models = field(default_factory=Models)

    def to_dict(self) -> dict[str, object]:
        """Return the effective settings, in the shape of `surface.json`."""
        return {
            "plans_dir": self.plans_dir,
            "max_autonomous_passes": self.max_autonomous_passes,
            "models": {f.name: getattr(self.models, f.name) for f in fields(self.models)},
        }


KNOWN_KEYS = tuple(f.name for f in fields(Settings))
KNOWN_ROLES = tuple(f.name for f in fields(Models))


def settings_path(project_root: Path) -> Path:
    return project_root / SETTINGS_FILE


def _unknown(kind: str, key: str, known: tuple[str, ...]) -> str:
    close = difflib.get_close_matches(key, known, n=1)
    hint = f" (did you mean {close[0]!r}?)" if close else ""
    return f"unknown {kind} {key!r}{hint}; known: {', '.join(known)}"


def _removed(key: str) -> str:
    return f"the setting {key!r} is gone: {REMOVED_KEYS[key]}; remove the key"


def _positive_int(key: str, value: object) -> int:
    if type(value) is not int or value < 1:
        message = f"{key} must be a whole number of at least 1, got {value!r}"
        raise SettingsError(message)
    return value


def _text(key: str, value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        message = f"{key} must be a non-empty text without surrounding spaces, got {value!r}"
        raise SettingsError(message)
    return value


def _plans_dir(value: object) -> str:
    text = _text("plans_dir", value)
    path = PurePosixPath(text)
    if path.is_absolute() or "\\" in text or ".." in path.parts or not path.parts:
        message = f"plans_dir must be a folder inside the project, got {text!r}"
        raise SettingsError(message)
    return path.as_posix()


def _models(value: object) -> Models:
    if not isinstance(value, dict):
        message = f"models must be an object, got {value!r}"
        raise SettingsError(message)
    chosen: dict[str, str] = {}
    for role, alias in cast("dict[object, object]", value).items():
        role_name = str(role)
        if role_name not in KNOWN_ROLES:
            raise SettingsError(_unknown("model role", role_name, KNOWN_ROLES))
        chosen[role_name] = _text(f"models.{role_name}", alias)
    return Models(**chosen)


def parse_settings(raw: dict[str, object]) -> Settings:
    """Build the effective settings from the content of a `surface.json`."""
    for key in raw:
        if key in REMOVED_KEYS:
            raise SettingsError(_removed(key))
        if key not in KNOWN_KEYS:
            raise SettingsError(_unknown("setting", key, KNOWN_KEYS))
    values: dict[str, object] = {}
    if "plans_dir" in raw:
        values["plans_dir"] = _plans_dir(raw["plans_dir"])
    if "max_autonomous_passes" in raw:
        values["max_autonomous_passes"] = _positive_int(
            "max_autonomous_passes", raw["max_autonomous_passes"]
        )
    if "models" in raw:
        values["models"] = _models(raw["models"])
    return Settings(**values)  # type: ignore[arg-type]


def load_settings(path: Path) -> Settings:
    """Read a `surface.json`; a missing file gives the defaults."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Settings()
    except (OSError, UnicodeDecodeError) as error:
        message = f"{path}: cannot be read: {error}"
        raise SettingsError(message) from error
    try:
        return parse_settings(loads_object(text))
    except (JsonError, SettingsError) as error:
        message = f"{path}: {error}"
        raise SettingsError(message) from error
