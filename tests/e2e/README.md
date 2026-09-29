# End to end tests

The chain run for real, headless, on a toy project: does a session driven by the prompts do what the README promises? The strategy is in `docs/adr/0025-end-to-end-on-a-toy-project.md`, and `docs/adr/0030-exploration-left-to-the-permission-mode.md` says why the sessions bypass permissions, in a container.

Every scenario is billed and takes minutes: run them on demand, before a release or after a change of the prompts, never in CI.

## What you need

- Docker. The sessions bypass permissions, which is not safe on your machine: a command could reach outside the toy folder. They run in the container of `tests/e2e/Dockerfile`, which holds Python 3.11, git, the `claude` CLI and pytest, under a user that is not root. `toy.py` refuses to start a session anywhere else.
- A token in your environment: `CLAUDE_CODE_OAUTH_TOKEN`, printed by `claude setup-token`, or `ANTHROPIC_API_KEY`. The container cannot use the login of your `claude` on the host, which macOS keeps in its keychain. The token is passed to `docker run` from your environment and never written in the image. Sessions use its account.

## The toy project

`toy/toy.py build <state> <dest>` makes `<dest>/shelf`, a git repository holding a small module (`shelf`, a list of books read from a JSON Lines file), its tests and a gate command, `python3 -m unittest discover -s tests -q`, with `<dest>/origin.git` as its bare remote. It installs the chain from this clone, then drives one plan folder, `docs/plans/<date>-csv-export/`, to the state asked for, recording each event through the installed state script. It prints the path of the project.

| State | What the project holds |
|---|---|
| `specs` | the main branch, the chain installed, no plan |
| `awaiting-approval` | the branch `feat/csv-export`, a plan drafted at revision 1 (two slices), pushed |
| `overview-modified` | revision 1 approved, slice 1 done, then a commit of the developer that edits `overview.md` |
| `developer-break` | both slices done, then a commit of the developer that adds an `isbn` column the overview leaves out |
| `ceiling` | both slices done with a defect the tests do not see (lines sorted by title only), `max_autonomous_passes: 1` |

`toy/toy.py run <project> <log> <prompt> [--resume <session id>]` runs one headless session in the project until it ends, killed after 30 minutes, keeps its stream of JSON events in `<log>`, then prints its exit code, its session id, its cost and its final message. The session leaves out your user settings and MCP servers, and bypasses permissions (`--permission-mode bypassPermissions`): nobody is there to answer a prompt, and what an agent runs to explore the code is left to the permission mode, not listed by the chain. `run` works in the container only; `build` costs nothing and works anywhere.

## The automated scenarios

```sh
export CLAUDE_CODE_OAUTH_TOKEN=...           # or ANTHROPIC_API_KEY
scripts/gate.sh e2e                          # every scenario
scripts/gate.sh e2e -k nominal
E2E_OUT=/some/folder scripts/gate.sh e2e     # logs somewhere else than .e2e/
```

The gate builds the image, mounts this clone read-only at `/clone` and the output folder at `/out`, then runs pytest in the container. The arguments after `e2e` go to pytest. The output folder is `.e2e/` at the root of the clone, ignored by git, or the one `E2E_OUT` names. Each test builds its own project and its bare remote under `basetemp/` in that folder, one folder per test, and keeps the streams of its sessions in `logs/` next to the project. pytest empties `basetemp/` at the start of each run: to keep a run, choose another `E2E_OUT` for the next one.

| Test | Start | Session | What must hold |
|---|---|---|---|
| `test_the_nominal_path_reaches_conform` | `awaiting-approval` | `/surface-execute` | `conform`, one approval, each slice done once, `conformity.md` |
| `test_a_session_killed_in_a_slice_resumes_it` | `awaiting-approval` | `/surface-execute`, killed once an executor has written code, then relaunched | the journal of the killed session kept as is, one approval, each slice done once, `conform` |
| `test_a_modified_overview_stops_the_loop` | `overview-modified` | `/surface-execute` | nothing recorded, still `executing`, the final message names the overview |
| `test_the_ceiling_hands_back_to_the_developer` | `ceiling` | `/surface-execute` | `blocked` after one review with findings |

`test_a_prepared_state_is_the_one_named` builds each state, and `test_a_session_bypasses_permissions_in_the_container_only` checks the command line of a session and its refusal outside the container: both cost nothing, and run without a token (`scripts/gate.sh e2e -k "prepared or bypasses"`).

A model may take another valid path from one run to the next: read the logs before blaming the chain.

## The interactive scenarios, by hand

Some scenarios need the developer's answers. Play them one session per answer: `run` prints the session id, and `--resume <session id>` gives the next answer to the same conversation. A fresh session, without `--resume`, is how a relaunch after a dead session is tested. To kill a session mid-way, run it in the background and kill its process group (`kill -9 -<pid>`), watching the plan folder to choose the moment.

They are played in the container too, from a shell in it, at the root of the clone:

```sh
mkdir -p .e2e
docker build --build-arg UID="$(id -u)" --tag control-surface-e2e --file tests/e2e/Dockerfile tests/e2e
docker run --rm -it --init --name e2e-manual \
  --env CLAUDE_CODE_OAUTH_TOKEN --env ANTHROPIC_API_KEY \
  --volume "$PWD:/clone:ro" --volume "$PWD/.e2e:/out" \
  control-surface-e2e bash
```

A second shell, to watch a plan folder or kill a session, is `docker exec -it e2e-manual bash`. The files stay on the host under `.e2e/`, and so do the projects the automated scenarios left under `.e2e/basetemp/`, at the same `/out` path, so their bare remotes still resolve.

The commands below run in the container and assume `toy=tests/e2e/toy/toy.py` and a scratch folder `work=/out/manual`.

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

From the project the ceiling test leaves blocked, under `/out/basetemp/`, copy the toy folder twice into `$work`. In one copy, relaunch `/surface-execute`: it records `resumed` and goes on with a fresh count. In the other, give an amendment with `/surface-plan`: it records `amendment-received` and drafts revision 2.
