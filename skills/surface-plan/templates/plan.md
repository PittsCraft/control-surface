# Plan: <feature>

Revision <N>. Execution instructions for the agents, slice by slice, drafted from `specs.md`, `exploration.md` and `interview.md` of the plan folder, and from the code. Written in the language `exploration.md` names in its repository rules: translate the headings, keep the markers and the `gates` tag as they are. The plan stays alive: an executor that deviates amends it in the commit of its code.

The agent that drafts the plan designs it and lays it out as it sees fit: the decisions and the options set aside, the tests, the risks, the assumptions taken instead of a question go where they read best, each as long as the feature needs, none filled for its own sake. The chain reads three things only, which the plan holds under the three headings below, whatever stands around them. No code beyond a signature or a schema fragment. The plan is committed and the repository's checks read it: every path is written from the root of the repository, never as a path of a machine, and a decision still to come or an option set aside is described, never cited by a record number that does not exist. The agent has no write tool: it returns the plan whole as its answer, and nothing around it, and the command that launched it writes `plan.md`.

The agent cannot ask the developer anything. One kind of assumption is therefore the developer's to confirm. It is a rule that a user of the feature, or a program that reads what it writes, would see applied: an order, ties included, a number, a frequency or a limit, who or what is counted or left out, what is refused. The plan settles such a rule on its own when neither the specs, an answer of the developer in `interview.md` nor the code, its closest precedent included, settles it: an assumption the interview wrote down without asking is no answer. Wherever the plan states that rule, an acceptance criterion included, it says so: an assumption of the plan, which approving the blueprint confirms. The blueprint then gives it to the developer as one, where a rule stated as settled would be one they never decided. A matter of implementation, which neither a user nor such a program would see, is no such assumption.

When `plan.md` already exists, the agent drafts its next revision, which carries every amendment and every accepted plan change of `interview.md`. A slice that a `slice-done` line of `journal.jsonl` records is built: it stays, under its number. What is left to build goes into the slices that have not run, or into new ones.

## Acceptance criteria

Numbered, taken from the specs and the interview: the blueprint carries them, and the review and the proof of conformity cite them by number.

## Slices

Each slice ships and verifies alone, in order. Each is enough for an agent that starts fresh, which reads files and never a conversation: what it delivers, what it touches, the precedent it copies, what proves it done. A slice says nothing of how its commit is written or signed beyond what the conventions of the repository or the developer ask: that commit is written by the agent that carries out the slice, not by the one that drafts the plan. Each is preceded by its marker, alone on its line and starting at the first column: the state script reads the list of slices from the markers, in any language. A slice number is never reused: a new slice takes a number above every number the plan has used. A marker quoted in prose is indented or kept inline.

<!-- slice:1 -->
### Slice 1: <title>

What the slice delivers, and what proves it done.

## Gates

The commands that check the whole project, which the state script runs after the slices and at every fix, in order, stopping at the first that fails. They are the gates `exploration.md` names for the plan, or those the developer named in `interview.md`, as they are: the command that launched the agent found them, and the agent does not choose them. One command per line in the block below, which starts at the first column and keeps its `gates` tag in any language. The block is empty when the project has none, and a sentence says so.

```gates
<command>
```
