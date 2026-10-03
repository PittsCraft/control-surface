# Evaluations

The tests hold the state script and the wording of the prompts, and the end to end tests hold that a real session reaches the expected state on a toy with one behavior. The evaluations answer what none of them does, after a change of the prompts: does the chain meet its goals, and is it good to work with. They run real sessions with no human in them, and produce a report that compares from one version of the prompts to the next. The decision and its reasons are in `docs/adr/0036-evaluations-on-real-sessions.md`.

They evaluate what the chain adds, not what the model does well alone: the detailed plan is left out, since its substance is the model's work.

Every command but `report` is billed and takes minutes to hours: run them on demand, after a change of the prompts, never in CI. Nothing fails and nothing has a threshold: the report says what the runs show and what moved, and you decide what to hold.

## What you need

What the end to end tests need (`tests/e2e/README.md`): Docker, and a token in your environment, `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY`. The sessions bypass permissions, so they run in the same container, and refuse to start anywhere else.

## The corpus

`evals/host/` is a synthetic host, richer than the toy: `lending`, a command line tool for a library, with several components, a state kept in files, and two critical zones declared in its `AGENTS.md`, the fine computation and the format of `loans.jsonl`. It is copied into a fresh repository for each run, with a bare remote, and the chain is installed in it from this clone.

`evals/cases/` holds one need per shape:

| Case | Shape | What it asks of the chain |
|---|---|---|
| `01-overdue-list` | one behavior | a blueprint of one section and no diagram |
| `02-reservations` | several flows | a body cut by flow, states to draw, then an amendment: the next revision keeps the cut |
| `03-overdue-reminders` | one flow across components | a body cut by component, an order between them to draw |
| `04-suspension` | a trade-off | a need of one sentence whose rules are the developer's: a threshold, what counts as owed |
| `05-fine-cap` | a critical zone touched | the zone named at approval, its file listed at conformity |
| `06-borrow-limit` | an ambiguous need | an interview that asks: the numbers are in nobody's code |

A case folder holds:

- `need.md`: what the developer types after `/surface-plan`.
- `brief.md`: what the developer knows and did not write. A model plays the developer from it: it answers the question a session ended on and nothing more, and leaves to the session what the brief leaves to the implementer. Handed the blueprint, it reads it and says what contradicts the brief, or that there is nothing to change.
- `acceptance/`: tests of the delivered code, through the command line, that the agents never see. They hold the need and the rules of the brief, so an interview that did not ask cannot pass them.
- `reference/`: an implementation, as files to lay over the host. It proves the acceptance tests fair: they fail on the host and pass on the reference, which the unit tests check.
- `case.json`: what a good run looks like: how many sections the body of the blueprint should have, whether the feature has a shape to draw, the critical zones it touches and their files, an amendment to give after the hand over.

The sessions run in the container, where this clone is mounted at `/clone`: a session that names `/clone` in a tool call has read what it must not, and its run is marked `contaminated`.

## A run

A run plays the developer's side of the README: the need, an answer to each question, then a reading of the blueprint handed over, whose corrections go back as amendments, twice at most. It gives the amendment of the case when it has one, replies with a sentence that agrees, "Looks fine to me, go ahead.", which must approve nothing, then launches `/surface-execute`, which approves. It stops when the plan is conformant or the loop hands back, runs the acceptance tests, and keeps everything under `runs/<case>/run-NN/`: the project, the stream of every session, each blueprint handed over, and `run.json`, what was said at each stop and the state of the plan then.

## The commands

```sh
export CLAUDE_CODE_OAUTH_TOKEN=...                       # or ANTHROPIC_API_KEY
scripts/gate.sh evals probes                             # faults put there on purpose, on the toy
scripts/gate.sh evals corpus --runs 3 --jobs 3           # every case, three runs each
scripts/gate.sh evals corpus --case 05-fine-cap          # one case
scripts/gate.sh evals judge-check                        # is the judge to be trusted
scripts/gate.sh evals judge                              # judge the runs not judged yet
python3 evals/run.py report                              # no session: runs anywhere
python3 evals/run.py report --against evals/reports/<kept>/summary.json --keep
```

The gate builds the image, mounts this clone read-only at `/clone` and the campaign folder at `/out`, and runs `evals/run.py` in the container. The campaign folder is `.evals/` at the root of the clone, ignored by git, or the one `EVALS_OUT` names. Commands add to it: run them one at a time, and choose another folder for another campaign.

`--max-usd` and `--max-week-points` stop a command before it starts a session past a ceiling. The folder keeps `ledger.json`: the cost at list price, which the stream of a session reports, and, on a subscription, how far the weekly gauge rose while sessions ran. That gauge moves by whole points and counts every use of the account meanwhile: it is a ceiling on the safe side, not a bill.

## Does it meet its goals

Computed by a script, from the plan folder, the journal, the streams and the delivered code (`surface_evals/measure.py`). Per run:

- **The loop converges, and hands back when it should**: the outcome, `conformant`, `handed-back`, or stuck in planning or in execution; the passes used; the reason of a hand back; and `approved_by_sentence`, which must stay false.
- **The interview frames the need**: `questions`, how many it asked, and `corrections`, how many blueprints the developer sent back because one contradicted what they knew: a rule the interview did not ask for and the plan guessed.
- **Conformant is true**: `acceptance`, the share of the acceptance tests the delivered code passes.
- **The critical zones**: `zones_named`, the blueprint names the zones the case touches; `zones_none_said`, it says none when there is none; `zones_files_listed`, the proof of conformity lists their files; `zones_consistent`, no file is listed for a zone the blueprint did not name.
- **The form of the blueprint**: `frame`, no numbered heading, the sections of its body against what the case expects, its diagrams against whether the feature has a shape, and `cut_kept` across the revisions of an amended case.
- **The plan**: drafted by the built-in agent, on which model, and holding the minimum the chain reads.

And on faults put there on purpose (`surface_evals/probes.py`), on the toy, whose documents and code are written out and so can be spoiled exactly:

- **The blueprint hides nothing**: a fresh checker, alone, cross-checks a blueprint that leaves out a column the plan exports, a critical zone it touches, an irreversible effect it has. It must find each, and find nothing on a faithful blueprint.
- **A fault is caught by the review, and classified right**: `/surface-execute` is launched on a branch that holds a defect the tests do not see, a deviation from the plan that keeps the blueprint true, a commit against the contract, and work as planned. It is stopped at its first review, whose counts the journal holds.

## Is it good to work with

Judged by a model against `evals/judge/rubric.md`, each judgement with its score from 1 to 5, its reason and the passage it rests on (`surface_evals/judge.py`). Four dimensions: the blueprint, for a developer who must decide; the interview, which frames the need; what the agents say; following along. The judge of the interview reads the code of the host as it was, to tell a question the code already answers. A passage that stands in no document it was given is marked as not grounded, and the report gives the share that is.

The judge is checked without a human (`surface_evals/judge_check.py`). `evals/judge/spoiled/` holds documents of the toy spoiled in one known way each, with the criterion that way must lower: a padded blueprint, one stripped of the rules the interview settled, an interview with questions the need and the code already answer. Each must score below its original. A spoiled document that does not is a criterion on which the judge is not to be trusted, and the report says so.

## The report

`report` measures every run of the campaign folder and writes `summary.json` and `report.md` in it. A measure is kept per case as its mean, its lowest and its highest value over the runs, since a model does not take the same path twice. With `--against`, it lists what moved since an earlier campaign: a measure moved when its values lie wholly outside those of the campaign before, so that the spread between runs is not read as a change, and it is called better or worse when it has a better way.

`--keep` copies both files to `evals/reports/<date>-<version of the chain>/`, to commit: that is what the next campaign is compared with. The version is a hash of `agents/` and `skills/`. The streams and the projects stay in the campaign folder, out of git.

Read a run before blaming the chain: a model may take another valid path, and an acceptance test may hold a rule the brief states badly.
