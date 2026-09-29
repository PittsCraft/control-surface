"""No skill, no agent names a host project or assumes its stack.

A denylist is a signal, not a proof: it catches the names that slip in, and the review reads the
rest. It covers the agents and, once they exist, the skills.
"""

import re
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from prompt_support import ROOT, prompt_files

# The owner of this repository, and places of one developer's machine. Private names and the
# paths of the author's machine are refused in every file of the repository by `test_privacy.py`.
HOSTS = ("PittsCraft",)
PERSONAL_PATHS = ("/home/", "~/", "Workspaces/", "topics/")
# Tools and languages of a stack: the chain reads a host's gates from its files, it never names
# them. Words that are also plain English (react, node, black, swift, make) are left to the review.
STACK = (
    "pytest",
    "unittest",
    "jest",
    "vitest",
    "mocha",
    "rspec",
    "phpunit",
    "junit",
    "npm",
    "npx",
    "yarn",
    "pnpm",
    "deno",
    "pip",
    "poetry",
    "uv",
    "uvx",
    "ruff",
    "mypy",
    "pyright",
    "flake8",
    "eslint",
    "prettier",
    "tsc",
    "cargo",
    "gradle",
    "mvn",
    "maven",
    "Makefile",
    "docker",
    "kubectl",
    "django",
    "fastapi",
    "rails",
    "xcodebuild",
    "dotnet",
    "typescript",
    "javascript",
    "java",
    "kotlin",
    "ruby",
    "php",
    "golang",
    "rust",
)
_WORDS = re.compile(
    r"(?<![\w-])(?:" + "|".join(re.escape(word) for word in HOSTS + STACK) + r")(?![\w-])",
    re.IGNORECASE,
)


def denied_terms(text: str) -> set[str]:
    found = {match.group(0) for match in _WORDS.finditer(text)}
    found.update(path for path in PERSONAL_PATHS if path in text)
    return found


def test_the_prompts_are_found() -> None:
    assert len(prompt_files()) >= 4


@pytest.mark.parametrize("path", prompt_files(), ids=lambda path: path.relative_to(ROOT).as_posix())
def test_no_host_name_personal_path_or_stack_tool(path: Path) -> None:
    assert denied_terms(path.read_text(encoding="utf-8")) == set()


@given(
    st.sampled_from(HOSTS + STACK + PERSONAL_PATHS),
    st.sampled_from([" ", "\n", "(", "`"]),
    st.sampled_from([" ", "\n", ".", ")", "`"]),
)
def test_the_detector_finds_an_inserted_term(term: str, before: str, after: str) -> None:
    text = f"Run the gates{before}{term}{after}then commit."
    assert denied_terms(text)


def test_the_detector_leaves_longer_words_alone() -> None:
    assert denied_terms("the pipeline, a uvula, a rusty javelin, a cargo-ship, pipes") == set()
