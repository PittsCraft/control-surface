# Architecture decisions

The current architecture is described in [ARCHITECTURE.md](../../ARCHITECTURE.md). The records here are the few decisions whose history matters: hard to reverse, structural or bearing on a key quality, chosen against credible alternatives, or likely to be "fixed" by someone who does not know why. Each has its context, the decision and its consequences. Numbers are kept when records are removed, so gaps are expected.

| # | Decision |
|---|---|
| 0001 | [Runtime floor Python 3.11, standard library only, no network](0001-python-311-standard-library.md) |
| 0011 | [State is a pure fold; guards split by what they need](0011-pure-fold-and-two-families-of-guards.md) |
| 0012 | [The script computes every derived field; the journal has one canonical form](0012-script-computes-derived-fields.md) |
| 0016 | [The plans of a branch, from git objects](0016-plans-of-a-branch-from-git-objects.md) |
| 0019 | [Ownership by namespace](0019-ownership-by-namespace.md) |
| 0025 | [End to end tests on a toy project, in a container, on demand](0025-end-to-end-on-a-toy-project.md) |
| 0031 | [The session's model and effort are the developer's; the chain pins only the agents' models](0031-session-model-left-to-the-developer.md) |
| 0032 | [Permissions left to the mode, no tests on the README](0032-permissions-left-to-the-mode-no-tests-on-the-readme.md) |
| 0033 | [A suspected break is kept in the journal until a reviewer judges it](0033-a-suspected-break-kept-in-the-journal.md) |
| 0034 | [Gates named by the plan, run by the script](0034-gates-named-by-the-plan-run-by-the-script.md) |
| 0035 | [The plan is drafted by Claude Code's built-in Plan agent, held to the minimum the chain reads](0035-plan-drafted-by-the-built-in-plan-agent.md) |
| 0036 | [Evaluations on real sessions, with a model as the developer and a judge that is checked](0036-evaluations-on-real-sessions.md) |
