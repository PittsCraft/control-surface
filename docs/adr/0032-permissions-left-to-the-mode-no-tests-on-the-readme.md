# 0032. Permissions left to the mode, no tests on the README

Status: accepted
Date: 2026-09-29

## Context

An unattended loop stops at the first command nobody approves. The commands grant the state script, git and `gh` in their `allowed-tools`, but that grant clears at the next turn (Claude Code documentation of skills, read on 2026-09-29), and the loop often goes on in a later turn, when a background agent hands back. The chain first had the README give a block of rules to paste into the project settings, with a test holding it against the commands' `allowed-tools`, and had the end to end harness allow those rules and nothing more. The runs kept stopping on commands agents chose to explore the code with, which depend on the model and on the host: closing that list is a race the chain cannot win. Claude Code already answers it with its permission modes. A session also cannot read the rules in force, which come from several settings files and the command line.

Several tests asserted the README's sentences and snippets. They held the text equal to itself, proved nothing about the product, and turned every rewording into a test edit.

## Decision

The chain ships no permission rule and checks none at launch. The README's Permissions section is a warning alone: the loop stops at every command the developer's rules or mode do not allow; run it in auto mode. The installer never writes the host's Claude Code settings, and ends by pointing at that section. The commands keep their `allowed-tools` for their first turn.

The prompts still run every command from the root of the repository as a plain command (no `cd`, no `git -C`, no command run by another, no expansion), since that serves a developer on the default mode.

No test asserts the README's prose. A test may still read it as an input the product handles, such as the installer that must not copy it.

## Consequences

A developer on the default mode approves the commands the loop runs, or grants them in their own settings; that is their permission mode's call, not the chain's. A new command in a prompt changes no documentation, and rewording the README changes no test: what the README says is read in review.
