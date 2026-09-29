# 0032. Permissions left to the mode, no tests on the README

Status: accepted
Date: 2026-09-29

## Context

The README's Permissions section kept a block of settings, the rules the commands grant in their `allowed-tools` for their first turn only (ADR 0028), which ADR 0030 reduced to what the prompts themselves require. A test held the block against those `allowed-tools`. In auto mode the block is not needed, and on the default mode the agents' exploration stops the loop anyway (ADR 0030): the block serves nobody.

Several tests read `README.md` and asserted its sentences, anchors and snippets: the Permissions section, the models the README recommends (ADR 0031), the one-line install and the CI snippet (ADR 0029). They held the text equal to itself, proved nothing about the product, and turned every rewording of the documentation into a test edit.

## Decision

The Permissions section keeps its heading and a warning alone: the loop stops at every command the developer's rules or mode do not allow, until they approve it; run it in auto mode. The block and its example of a gate command are dropped. The commands keep their `allowed-tools` for their first turn, and the installer still ends by pointing at the section.

No test asserts the README's prose: the tests of the Permissions section, of the recommended models, of the one-line install block and of the CI snippet are dropped. A test may still read the README as an input the product handles, such as the installer that must not copy it into the host.

This amends ADR 0028, whose README gave the block and a test held it; ADR 0030, which kept the block and its test; ADR 0021, whose README section granted in the settings what the command grants for its first turn; ADR 0029, whose test held the CI snippet; and ADR 0031, whose tests held the README's recommendation.

## Consequences

A developer on the default mode approves the commands the loop runs, or grants them in their own settings. A new command in a prompt changes no documentation, and rewording the README changes no test: what the README says is read in review.
