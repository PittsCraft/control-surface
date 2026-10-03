# 0035. The plan is drafted by Claude Code's built-in Plan agent, held to the minimum the chain reads

Status: accepted
Date: 2026-10-03

## Context

`/surface-plan` wrote `plan.md` itself, from a template of seven numbered sections: goal and scope, architecture decisions, slices, tests, definition of done, risks and assumptions, gates. Nothing in the chain read most of that form. The state script reads the slice markers and the `gates` block; the extractor, the checker and the reviewer read the acceptance criteria; an executor reads its slice. What the template held beyond that, a good plan, is what the `Plan` agent built into Claude Code already produces: it explores the code and designs an implementation, read only, and it follows the releases of Claude Code without the chain doing anything.

Two other ways were open. Keeping the command as the writer left the plan to the session that held the interview, on a form the chain had to maintain. An agent of the chain's own, a fifth definition, would have been one more prompt to keep at the state of the art, for the one step where the chain adds nothing.

## Decision

The plan is drafted by the built-in `Plan` agent, launched fresh by `/surface-plan` like the other agents, with a prompt of file paths only: the plan folder and `templates/plan.md`. The chain ships no definition for it, so that template is its whole mandate. It holds the plan to the minimum the chain reads, and leaves the rest, the design and its layout, to the agent:

- the acceptance criteria, numbered, taken from the specs and the interview;
- the slices, each behind its `<!-- slice:N -->` marker and enough for an agent that starts fresh, a number never reused and the slices already done kept across revisions;
- the `gates` block, which holds the commands `/surface-plan` found: the agent does not choose them, and the command corrects the block;
- the language `exploration.md` names, and no code beyond a signature or a schema fragment.

The agent has no write tool: it returns the plan, and the command writes `plan.md` as returned, then checks that minimum and nothing else. The command's own exploration shrinks to what the interview needs and to the repository rules every agent reads; the path through the code is the agent's. The approval does not move: the developer approves the blueprint, never the plan, so the plan mode of Claude Code, where a developer approves a plan, is not used.

The agent runs on the role `planner` of `models`, `opus` by default, passed on the Agent call as for the roles of the chain (ADR 0031). With no definition, nothing carries that default nor an effort: it runs at the session's effort.

The plans it drafts are not judged, no more than those the command wrote. The cross-check still compares the blueprint with the plan, and the tests hold only that the chain works with such plans: the contract of the prompts, and the end to end scenarios.

## Consequences

One prompt less to write and maintain, and plans that improve with Claude Code. The form of a plan is no longer fixed: no prompt names a section of a plan by a number, nor counts on a heading beyond the three of the template, and two plans may be laid out two ways. The chain depends on an agent it does not own: a release that renames it, removes it or changes what it returns changes this step, and in a host that denies it planning stops at the plan, where the command says so. A plan costs one more agent launch, and the code the feature touches is read twice, by the command for the interview and by the agent for the plan.
