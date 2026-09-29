# End to end tests

The chain run for real, headless, on a toy project: does a session driven by the prompts do what the README promises? The strategy is in `docs/adr/0025-end-to-end-on-a-toy-project.md`.

Every scenario is billed and takes minutes: run them on demand, before a release or after a change of the prompts, never in CI.

## What you need

- The `claude` CLI on the `PATH`, logged in. Sessions use your account.
- `python3` 3.11 or newer, `git`.

## The toy project

`toy/toy.py build <state> <dest>` makes `<dest>/shelf`, a git repository holding a small module (`shelf`, a list of books read from a JSON Lines file), its tests and a gate command, `python3 -m unittest discover -s tests -q`, with `<dest>/origin.git` as its bare remote. It installs the chain from this clone, then drives one plan folder, `docs/plans/<date>-csv-export/`, to the state asked for, recording each event through the installed state script. It prints the path of the project.

| State | What the project holds |
|---|---|
| `specs` | the main branch, the chain installed, no plan |
| `awaiting-approval` | the branch `feat/csv-export`, a plan drafted at revision 1 (two slices), pushed |
| `overview-modified` | revision 1 approved, slice 1 done, then a commit of the developer that edits `overview.md` |
| `developer-break` | both slices done, then a commit of the developer that adds an `isbn` column the overview leaves out |
| `ceiling` | both slices done with a defect the tests do not see (lines sorted by title only), `max_autonomous_passes: 1` |

`toy/toy.py run <project> <log> <prompt> [--resume <session id>]` runs one headless session in the project until it ends, killed after 30 minutes, keeps its stream of JSON events in `<log>`, then prints its exit code, its session id, its cost and its final message. The session leaves out your user settings and MCP servers, and may edit files and run what the Permissions section of the README allows, the toy's gate command, the branch commands of `/surface-plan` and the usual reading commands of the shell (`cat`, `ls`, `grep`, `mkdir` and the like): anything else is denied, since nobody is there to answer a prompt. A denial in a log is therefore a finding on the chain or on that section.

## The automated scenarios

```sh
scripts/gate.sh e2e                          # every scenario
scripts/gate.sh e2e -k nominal --basetemp /some/empty/folder
```

The arguments after `e2e` go to pytest. Each test builds its own project under pytest's temporary folder, `--basetemp` when given, and keeps the streams of its sessions in `logs/` next to it.

| Test | Start | Session | What must hold |
|---|---|---|---|
| `test_the_nominal_path_reaches_conform` | `awaiting-approval` | `/surface-execute` | `conform`, one approval, each slice done once, `conformity.md` |
| `test_a_session_killed_in_a_slice_resumes_it` | `awaiting-approval` | `/surface-execute`, killed once an executor has written code, then relaunched | the journal of the killed session kept as is, one approval, each slice done once, `conform` |
| `test_a_modified_overview_stops_the_loop` | `overview-modified` | `/surface-execute` | nothing recorded, still `executing`, the final message names the overview |
| `test_the_ceiling_hands_back_to_the_developer` | `ceiling` | `/surface-execute` | `blocked` after one review with findings |

`test_a_prepared_state_is_the_one_named` builds each state and costs nothing.

A model may take another valid path from one run to the next: read the logs before blaming the chain.

## The interactive scenarios, by hand

Some scenarios need the developer's answers. Play them one session per answer: `run` prints the session id, and `--resume <session id>` gives the next answer to the same conversation. A fresh session, without `--resume`, is how a relaunch after a dead session is tested. To kill a session mid-way, run it in the background and kill its process group (`kill -9 -<pid>`), watching the plan folder to choose the moment.

The commands below assume `toy=tests/e2e/toy/toy.py` and a scratch folder `$work`.

### Planning from the specs, killed during the interview

```sh
p=$(python3 $toy build specs $work/plan)
python3 $toy run $p $work/plan-1.jsonl "/surface-plan Export the shelf as CSV for the bookshop: title, author and year, sorted by author then title."
```

The session explores, writes `exploration.md`, then asks its first question and stops. Answer it with `--resume`. Kill the session that takes the answer as soon as the answer is in `interview.md`. Then relaunch without `--resume`, with `/surface-plan` alone:

- it must not explore again, nor ask again a question that has an answer: it asks the next open one;
- answered to the end, it writes the plan, has the overview drawn and cross-checked, records `plan-drafted`, commits and pushes to the bare remote. `gh` cannot open a pull request on a local remote: the session says so and gives the description.

### An amendment, killed right after it was recorded

```sh
p=$(python3 $toy build awaiting-approval $work/amend)
python3 $toy run $p $work/amend-1.jsonl "/surface-plan Put the year first: year, title, author."
```

Run it in the background and kill it as soon as `journal.jsonl` holds `amendment-received`. Then relaunch with `/surface-plan` alone. The amendment must be under "Amendments" in `interview.md` and in the journal, and revision 2 of `plan.md` and `overview.md` must carry it.

### A break raised on a commit of the developer, then refused

```sh
p=$(python3 $toy build developer-break $work/break)
python3 $toy run $p $work/break-1.jsonl /surface-execute
```

The review must raise a contract break on the `isbn` column, with a proposal under `plan-changes/`, and the loop stops in `plan-change-proposed`. Then `/surface-plan` presents the proposal and asks: answer with `--resume` that you refuse it, and why. Relaunch `/surface-execute`: the fix brings the code back to the overview, and no later review raises the same break again.

### The ceiling, then both ways on

From the project the ceiling test leaves blocked, copy the toy folder twice. In one copy, relaunch `/surface-execute`: it records `resumed` and goes on with a fresh count. In the other, give an amendment with `/surface-plan`: it records `amendment-received` and drafts revision 2.
