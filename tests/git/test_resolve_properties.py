"""Property: resolution follows what each command accepts, whatever the plans on main and branch."""

import tempfile
from pathlib import Path

import pytest
from git_support import Repo, isolate_git
from hypothesis import given, settings
from hypothesis import strategies as st

# Restated independently: what each command accepts among the reachable states (ADR 0015).
ACCEPTS = {
    "plan": {"interview", "drafting", "awaiting-approval"},
    "execute": {"awaiting-approval", "executing", "reviewing"},
}
STATES = ["interview", "drafting", "awaiting-approval", "executing", "reviewing", "conform"]
NAMES = [f"2026-09-{day:02d}-plan" for day in range(1, 9)]


@pytest.fixture(autouse=True)
def _git_env(monkeypatch: pytest.MonkeyPatch) -> None:
    isolate_git(monkeypatch)


@settings(max_examples=25, deadline=None)
@given(
    on_main=st.dictionaries(st.sampled_from(NAMES[:4]), st.sampled_from(STATES), max_size=4),
    on_branch=st.dictionaries(st.sampled_from(NAMES[4:]), st.sampled_from(STATES), max_size=4),
    command=st.sampled_from(["plan", "execute"]),
    committed=st.booleans(),
)
def test_the_branch_plans_of_the_right_state_are_the_candidates(
    on_main: dict[str, str], on_branch: dict[str, str], command: str, *, committed: bool
) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Repo(Path(tmp))
        for name, state in on_main.items():
            repo.plan(state, name)
        repo.commit("plans kept on main")
        repo.branch("feature")
        for name, state in on_branch.items():
            repo.plan(state, name)
        if committed:
            repo.commit("plans of the branch")
        expected = sorted(name for name, state in on_branch.items() if state in ACCEPTS[command])
        result = repo.resolve(command)
        payload = result.json()
        assert [item["name"] for item in payload["candidates"]] == expected
        assert repo.names() == sorted(on_branch)
        if len(expected) == 1:
            assert (result.code, payload["plan"], payload["outcome"]) == (0, expected[0], "one")
        else:
            assert result.code == 1
            assert payload["plan"] is None
            assert payload["outcome"] == ("several" if expected else "none")
        for name in (*on_main, *on_branch):
            assert repo.resolve(command, name).json()["plan"] == name
