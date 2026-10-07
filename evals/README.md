# Evaluations

The tests hold the state script and the wording of the prompts, and the end to end tests hold that a real session reaches the expected state on a toy with one behavior. The evaluations answer what none of them does, after a change of the prompts: does the chain meet its goals, and is it good to work with. They run real sessions with no human in them, and produce a report that compares from one version of the prompts to the next. The decision and its reasons are in `docs/adr/0036-evaluations-on-real-sessions.md`.

They evaluate what the chain adds, not what the model does well alone: the detailed plan is left out, since its substance is the model's work.

Every command but `report` is billed and takes minutes to hours: run them on demand, after a change of the prompts, never in CI. Nothing fails and nothing has a threshold: the report says what the runs show and what moved, and you decide what to hold.

## What you need

What the end to end tests need (`tests/e2e/README.md`): Docker, and a token in your environment, `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY`. The sessions bypass permissions, so they run in the same container, and refuse to start anywhere else. That container reaches no GitHub: a stand-in for `gh` plays the pull request steps of the chain and records every call, so that these steps are run and measured, and no message has a missing `gh` to tell. What the stand-in answers and what it does not imitate is in `tests/e2e/README.md`.

## The corpus

`evals/host/` is a synthetic host, richer than the toy: `lending`, a command line tool for a library, with several components, a state kept in files, and two critical zones declared in its `AGENTS.md`, the fine computation and the format of `loans.jsonl`. It is copied into a fresh repository for each run, with a bare remote, and the chain is installed in it from this clone.

`evals/cases/` holds one need per shape:

| Case | Shape | What it asks of the chain |
|---|---|---|
| `01-overdue-list` | one behavior | a blueprint of one section and no diagram |
| `02-reservations` | several flows | a body cut by flow, states to draw, then an amendment: the next revision keeps the cut |
| `03-overdue-reminders` | one flow across components | a body cut by component, an order between them to draw; and, since its need states the wrong rule on purpose, a blueprint that lets the developer catch it |
| `04-suspension` | a trade-off | a need of one sentence whose rules are the developer's: a threshold, what counts as owed |
| `05-fine-cap` | a critical zone touched | the zone named at approval, its file listed at conformity |
| `06-borrow-limit` | an ambiguous need | an interview that asks: the numbers are in nobody's code |

A case folder holds:

- `need.md`: what the developer types after `/surface-plan`.
- `brief.md`: what the developer knows and did not write. A model plays the developer from it: it answers the question a session ended on and nothing more, and leaves to the session what the brief leaves to the implementer. Handed the blueprint, it reads it and says what contradicts the brief, or that there is nothing to change.
- `acceptance/`: tests of the delivered code, through the command line, that the agents never see. They hold the need and the rules of the brief, so an interview that did not ask cannot pass them.
- `reference/`: an implementation, as files to lay over the host. It proves the acceptance tests fair: they fail on the host and pass on the reference, which the unit tests check.
- `case.json`: what a good run looks like: how many sections the body of the blueprint should have, whether the feature has a shape to draw, the critical zones it touches and their files, an amendment to give after the hand over, a correction the case expects.

One case states the wrong rule on purpose. The need of `03-overdue-reminders` says that no member is reminded twice on the same day, and its developer means 7 days or more between two reminders of a member. It is not a slip of the corpus: the need reads as complete, a session that takes it at its word asks nothing and plans the same-day rule, and what the case evaluates is that the developer catches the error when they read the blueprint, before any code. So every run of it is expected to send one blueprint back. `case.json` says so under `expected_correction`, with the words that tell that correction among the others, the report tells it apart, and the README of the case says the same to whoever opens its folder.

The sessions run in the container, where this clone is mounted at `/clone`: a session that names `/clone` in a tool call has read what it must not, and its run is marked `contaminated`.

## A run

A run plays the developer's side of the README: the need, an answer to each question, then a reading of the blueprint handed over, whose corrections go back as amendments, twice at most. It gives the amendment of the case when it has one, replies with a sentence that agrees, "Looks fine to me, go ahead.", which must approve nothing, then launches `/surface-execute`, which approves. It stops when the plan is conformant or the loop hands back, runs the acceptance tests, and keeps everything under `runs/<case>/run-NN/`: the project, the stream of every session, each blueprint handed over, and `run.json`, what was said at each stop, the state of the plan then, and the pull request of the branch then, as the stand-in `gh` keeps it: whether it is a draft, and whether its description is the one `surface-status pr-body` prints at that moment. The calls themselves stay in the project, in `.git/gh-stand-in/calls.jsonl`.

`corpus --stop-at-hand-over` stops each run at the hand over, for a campaign that measures a change of planning alone, the interview or the blueprint, without paying for the execution. The run plays planning as above, the sentence that agrees included, since it is one cheap turn and `approved_by_sentence` is a measure of planning. It then launches nothing and runs no acceptance test. Its outcome is `stopped-at-hand-over`, which no run played whole has, and its `run.json` says `stop_at_hand_over`.

Nothing of the execution is read from such a run, whatever its outcome. Every measure the execution gives or adds to is empty for it, not 0 or false, so that it is never read as a run that failed to conform, nor counted with the runs played whole: `conformant`, `acceptance`, `gate`, the approvals, the reviews and their findings, the fixes, the failed gate runs, the sessions killed or relaunched, the files of the critical zones, `pr_refreshed`, `pr_marked_ready`, and `usd`. Of the pull request, such a run keeps what planning gives: the draft at the hand over, its description there, and the calls the stand-in did not play, which say how far to trust the run as `contaminated` does. Never marked ready is a promise to the end of the chain, and the hand back at conformity, where a chain would break it, is not reached: a false would claim what was not played. A pull request that planning marked ready still shows, since it is no draft at the hand over. `planning_usd`, what planning cost, is the one cost both kinds of runs have. The judge is asked the blueprint and the interview as for any run, since both are whole at the hand over: those scores compare with a campaign played whole. It is asked the messages and following along of planning alone, and told that the run stops there; it keeps those scores under names of their own, `messages-in-planning` and `following-in-planning`, since they answer another question than those of a run judged to its end. The report says how many runs played planning alone, and compares with another campaign only what both measured.

## The commands

```sh
export CLAUDE_CODE_OAUTH_TOKEN=...                       # or ANTHROPIC_API_KEY
scripts/gate.sh evals probes                             # faults put there on purpose, on the toy
scripts/gate.sh evals corpus --runs 3 --jobs 3           # every case, three runs each
scripts/gate.sh evals corpus --case 05-fine-cap          # one case
scripts/gate.sh evals corpus --stop-at-hand-over         # planning alone: no execution
scripts/gate.sh evals judge-check                        # are the judge and its count to be trusted
scripts/gate.sh evals judge                              # judge and count the runs not done yet
python3 evals/run.py report                              # no session: runs anywhere
python3 evals/run.py report --against evals/reports/<kept>/summary.json --keep
```

The gate builds the image, mounts this clone read-only at `/clone` and the campaign folder at `/out`, and runs `evals/run.py` in the container. The campaign folder is `.evals/` at the root of the clone, ignored by git, or the one `EVALS_OUT` names. Commands add to it: run them one at a time, and choose another folder for another campaign.

`--max-usd` and `--max-week-points` stop a command before it starts a session past a ceiling. The folder keeps `ledger.json`: the cost at list price, which the stream of a session reports, and, on a subscription, how far the weekly gauge rose while sessions ran. That gauge moves by whole points and counts every use of the account meanwhile: it is a ceiling on the safe side, not a bill. Runs played together note their sessions as each one ends, so a reading of the gauge may be older than the last one counted: a reading counts for what it stands above the highest of its week, which a stream dates, and a point is counted once.

## Does it meet its goals

Computed by a script, from the plan folder, the journal, the streams, the delivered code and what the stand-in `gh` kept (`surface_evals/measure.py`). Per run:

- **The loop converges, and hands back when it should**: the outcome, `conformant`, `handed-back`, or stuck in planning or in execution; the passes used; the reason of a hand back; and `approved_by_sentence`, which must stay false.
- **The interview frames the need**: `questions`, how many it asked; `questions_handed_back`, how many of them the developer handed back, whole or in part, as not theirs to decide: a question the interview asked and the brief leaves to the implementer. It is read from the words the rules of the developer give for it, "the assistant's call" or "your call", so every run kept has it, and an answer that leaves the choice in other words is not counted. The report tells it and never calls it better or worse: a developer may leave a choice to the session, and the brief of a case may play one who does; `corrections`, how many blueprints the developer sent back because one contradicted what they knew: a rule the interview did not ask for and the plan guessed; and `expected_correction`, on a case whose need states the wrong rule, whether a blueprint was sent back with the rule the developer meant. That one is left out of `corrections`, since no interview could have spared it. It is false when no blueprint came back with that rule: read `acceptance` then, which tells a rule that went through wrong from one the plan held right from the start.
- **Conformant is true**: `acceptance`, the share of the acceptance tests the delivered code passes.
- **The pull request**: `pr_draft_at_hand_over`, at every hand over, from the first, which follows the first `plan-drafted`, the branch has a pull request and it is a draft; `pr_described`, at the stops of planning that found a pull request, its description is the one `surface-status pr-body` prints then; `pr_refreshed`, the same at the stops of the loop, which each refresh it; `pr_marked_ready`, a call asked to mark it ready, which must stay false; `gh_not_played`, how many calls the stand-in could not answer as `gh` would, after which a message may speak of the stand-in and not of the chain. The description is read where the prompts push and refresh it, on a plan awaiting approval, blocked, with a plan change proposed, or conformant: a session that ends on a question while it drafts a revision has pushed nothing yet, and one killed at the timeout, which `killed` counts, reached no stop. A run kept before the stand-in has none of the five.
- **The critical zones**: `zones_named`, the blueprint names the zones the case touches; `zones_none_said`, it says none when there is none; `zones_files_listed`, the proof of conformity lists their files; `zones_consistent`, no file is listed for a zone the blueprint did not name.
- **The form of the blueprint**: `frame`, no numbered heading, the sections of its body against what the case expects, its diagrams against whether the feature has a shape, and `cut_kept` across the revisions of an amended case.
- **The plan**: drafted by the built-in agent, on which model, and holding the minimum the chain reads.

And on faults put there on purpose (`surface_evals/probes.py`), on the toy, whose documents and code are written out and so can be spoiled exactly:

- **The blueprint hides nothing**: a fresh checker, alone, cross-checks a blueprint that leaves out a column the plan exports, a critical zone it touches, an irreversible effect it has. It must find each, and find nothing on a faithful blueprint.
- **A fault is caught by the review, and classified right**: `/surface-execute` is launched on a branch that holds a defect the tests do not see, a deviation from the plan that keeps the blueprint true, a commit against the contract, and work as planned. It is stopped at its first review, whose counts the journal holds.

## Is it good to work with

Judged by a model against `evals/judge/rubric.md`, each judgement with its score from 1 to 5, its reason and the passage it rests on (`surface_evals/judge.py`). Four dimensions: the blueprint, for a developer who must decide; the interview, which frames the need; what the agents say; following along. The judge of the interview reads the code of the host as it was, to tell a question the code already answers. A passage that stands in no document it was given is marked as not grounded, and the report gives the share that is.

The rubric says where the chain does on purpose what a strict reader would fault, so that the judge and the prompts hold the same idea of a good run:

- `blueprint.no-padding`: what the frame of a blueprint asks for is not padding: the closing line, the statement of the critical zones, and the boundaries between components, which are the developer's to decide.
- `blueprint.diagrams`: a diagram may draw what the prose says where the shape is real, and a chain with a single fork is no shape.
- `messages.clear`: the words of the chain that its README and its guide teach are the developer's, and a message may use them. The name of any agent but the reviewer and the paths of the reports are the chain's insides, which a final message keeps out. The blueprint and a plan change proposal are no reports, and the description of the pull request, which a script writes, links the files it lists.
- `following.no-noise`: saying at every hand over, and in reply to a sentence that agrees, that only the launch of `/surface-execute` approves is the point, not noise.

The judge is checked without a human (`surface_evals/judge_check.py`). `evals/judge/spoiled/` holds documents of the toy spoiled in one known way each, with the criterion that way must lower: a padded blueprint, one stripped of the rules the interview settled, an interview with questions the need and the code already answer. Each must score below its original. A spoiled document that does not is a criterion on which the judge is not to be trusted, and the report says so. The padded blueprint is padded from a lean one of its own, since padding added to a page that already repeats itself shows nothing.

### What the developer would skip, counted

A score from 1 to 5 is too coarse to follow a change of the blueprint: `blueprint.no-padding` gave the same score to pages on which a reader who counted found thirteen to fifteen facts said twice, then two to four. So the judge also counts (`surface_evals/count.py`), in a call of its own that leaves the criteria of the rubric as they are asked. It is given the blueprint alone and the method of `evals/judge/count.md`, the one that reader followed by hand. Per run:

- `repeated_in_prose`: the facts the page states more than once in prose. A later passage that adds a reason, a consequence, an edge case or a worked example is not a repeat, nor is a pointer to a criterion, nor are two lines of the frame, the bare line of the critical zones and the closing line. A fact that only a diagram draws again is listed and not counted, since a diagram may draw what the prose says.
- `implementation_details`: the details of implementation that are not the developer's to decide: the name of a function, a constant or a helper, a call to a library, where a piece of code sits in a file. The boundaries between components, which component calls which and what each answers for, are theirs to decide and are not counted.
- `skippable_percent`: the share of the words of the page the developer could skip, the judge's estimate, to the nearest five. It tells what the two counts cannot, a page padded with whole sections: the padded page of the check says fewer facts twice than a long blueprint does, and holds far more to skip.

Lower is better for each. The two counts are made by the script, from lists: the judge gives each fact with every statement of it, its place on the page and the passage that makes it, and each detail with its passage, never a total. `count.json`, in the folder of the run, keeps them: a count is checked by reading its passages against the page. The script holds the rest of what it can. An answer that is not the lists and the share asked for is refused. A passage that is not on the page is marked, one given twice for the same fact counts twice only where the page holds it twice, and `count_grounded` is the share of the passages that stand. A passage that only a diagram of the page holds is a statement in a diagram, whatever place the judge gave it, so that a diagram's line is never a repeat in prose. A run that handed no blueprint over has no count, where a zero would read as the best of pages. A run that stopped at the hand over has its blueprint, whole: it is counted like any other, under the same names, and its counts join the same spread.

The count is checked on the lean blueprint and its padded version: each of the three must be higher on the padded page. One that is not is a measure on which the judge is not to be trusted.

To read them: a fact has no sharp edge, and two readings of the same page by hand differed by one fact in seven, so one or two facts between two runs say nothing. For scale, by hand and by this method: 0, 0 and 0% on the lean page; 6 or 7 facts, 7 details and 60% on the padded one; 7 to 18 facts, 4 to 9 details and 25 to 40% on the blueprints of the second campaign; 2 to 6, 1 to 5 and 10 to 25% once the extractor was told to say a fact once. These figures were counted before the method set aside two lines of the frame and the boundaries between components: a page counted today may count a little less.

Not counted, of what that reader gave: a score of its own, which would be a second score of `blueprint.no-padding`; what is missing to decide, which `blueprint.decidable` asks with the need and the interview in hand, and which no passage of the page can show; the facts only a diagram repeats, as a measure, which it called coarser and which the check cannot hold, since it found none on the padded page.

## The report

`report` measures every run of the campaign folder and writes `summary.json` and `report.md` in it. A measure is kept per case as its mean, its lowest and its highest value over the runs, since a model does not take the same path twice. Under the scores of the judge, it gives the lowest judgement of each criterion with its reason and its passage: that is where to start reading. The counts of the blueprint follow, measures like the others. With `--against`, it lists what moved since an earlier campaign: a measure moved when its values lie wholly outside those of the campaign before, so that the spread between runs is not read as a change, and it is called better or worse when it has a better way.

A campaign judged before the judge counted holds no count. Compared with one that does, the report says that the counts are not compared, where "nothing moved" would read as counts that stayed where they were. Its runs can still be counted: `judge` keeps the scores in `judge.json` and the counts in `count.json`, and makes only the one a run lacks, so the scores of an old campaign stay as they were.

`--keep` copies both files to `evals/reports/<date>-<version of the chain>/`, to commit: that is what the next campaign is compared with. The version is a hash of `agents/` and `skills/`. The streams and the projects stay in the campaign folder, out of git.

The campaigns kept before the stand-in `gh`, `evals/reports/2026-10-03-*`, were played in an image with no `gh`: every hand over said so, and the judge scored it. Against one of them, a move of the scores of the messages may come from the stand-in, which the hash of the chain does not show, and not from the prompts.

The four campaigns kept in `evals/reports/2026-10-03-*` and `2026-10-05-*` were judged before the rubric drew the four lines above, and the one that holds counts, `2026-10-05-*`, was counted before the method set aside what the frame asks for. Against one of them, a move of `blueprint.no-padding`, `blueprint.diagrams`, `messages.clear`, `following.no-noise` or of a count may come from the judge, which the hash of the chain does not show either.

The four campaigns kept in `evals/reports/2026-10-03-*` and `2026-10-05-*` counted a point of the weekly gauge again each time runs played together reported it out of order, since a lower reading was taken for a week that turned. Read again in their streams, the gauge rose by 1, 2 and 1 points while the three campaigns of `2026-10-03-*` ran, where their reports say 3, 5 and 5.

The summaries kept before `03-overdue-reminders` said that it expects a correction count that one among its `corrections`. Against one of them, the report compares neither the `corrections` of that case nor those of all the runs, and says so.

Read a run before blaming the chain: a model may take another valid path, and an acceptance test may hold a rule the brief states badly.
