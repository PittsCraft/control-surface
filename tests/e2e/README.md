# End to end tests

The chain run for real, headless, on a toy project: does a session driven by the prompts do what the README promises? The strategy, and why the sessions bypass permissions in a container, is in `docs/adr/0025-end-to-end-on-a-toy-project.md`.

Every scenario is billed and takes minutes: run them on demand, before a release or after a change of the prompts, never in CI.

## What you need

- Docker. The sessions bypass permissions, which is not safe on your machine: a command could reach outside the toy folder. They run in the container of `tests/e2e/Dockerfile`, which holds Python 3.11, git, the `claude` CLI, pytest and a stand-in for `gh`, under a user that is not root. `toy.py` refuses to start a session anywhere else.
- A token in your environment: `CLAUDE_CODE_OAUTH_TOKEN`, printed by `claude setup-token`, or `ANTHROPIC_API_KEY`. The container cannot use the login of your `claude` on the host, which macOS keeps in its keychain. The token is passed to `docker run` from your environment and never written in the image. Sessions use its account.

## The toy project

`toy/toy.py build <state> <dest>` makes `<dest>/shelf`, a git repository holding a small module (`shelf`, a list of books read from a JSON Lines file), its tests, an `AGENTS.md` that declares the CSV export a critical zone, and a gate command, `python3 -m unittest discover -s tests -q`, with `<dest>/origin.git` as its bare remote. It installs the chain from this clone, then drives one plan folder, `docs/plans/<date>-csv-export/`, to the state asked for, recording each event through the installed state script. It prints the path of the project.

| State | What the project holds |
|---|---|
| `specs` | the main branch, the chain installed, no plan |
| `awaiting-approval` | the branch `feat/csv-export`, a plan drafted at revision 1 (two slices), pushed, and its draft pull request, open in the stand-in `gh` |
| `blueprint-modified` | revision 1 approved, slice 1 done, then a commit of the developer that edits `blueprint.md` |
| `developer-break` | both slices done, then a commit of the developer that adds an `isbn` column the blueprint leaves out |
| `ceiling` | both slices done with a defect the tests do not see (lines sorted by title only), a first review that found it, then a fix that missed it, `max_autonomous_passes: 1` |
| `done`, `defect`, `deviation` | both slices done and nothing reviewed yet: as planned, with that same defect, or with the tests of slice 1 in another file than the plan names. The evaluations review them (`evals/README.md`) |

`toy/toy.py run <project> <log> <prompt> [--resume <session id>]` runs one headless session in the project until it ends, killed after 30 minutes, keeps its stream of JSON events in `<log>`, then prints its exit code, its session id, its cost and its final message. The session leaves out your user settings and MCP servers, and bypasses permissions (`--permission-mode bypassPermissions`): nobody is there to answer a prompt, and what an agent runs to explore the code is left to the permission mode, not listed by the chain. `run` works in the container only; `build` costs nothing and works anywhere.

## The stand-in `gh`

The container reaches no GitHub, and a project pushes to a bare repository on disk, on which the real `gh` opens no pull request. So the image holds a stand-in, `toy/gh_stand_in.py`, copied to `/opt/gh-stand-in/gh`, first on the `PATH`: a session plays the pull request steps of the chain, and the harness reads what was asked. The evaluations run in the same image and measure the same record (`evals/README.md`).

It answers the calls the prompts make, as `gh` 2.78.0 does when its output is not a terminal, on the repository of the current directory:

| Call | What the stand-in does |
|---|---|
| `gh pr create --title <title> --body <text>`, or `--body-file <file>`, or `--body-file -`, with `--draft`, `--base`, `--head` | opens a pull request for the current branch and prints its address. Refused without a title and a description, when the remote does not hold the last commit of the branch, when the branch has nothing to merge, and when a pull request is already open for it into the same base |
| `gh pr edit`, with a number, an address or a branch, and `--title`, `--body`, `--body-file`, `--base` | replaces the title or the description and prints the address. Fails with `no pull requests found for branch "<branch>"` when the branch has none |
| `gh pr list`, with `--state`, `--author`, `--head`, `--base`, `--draft`, `--limit`, `--json`, `--jq` | lists the pull requests, the last opened first, in the fields asked |
| `gh pr view`, with a number, an address or a branch, and `--json`, `--jq` | shows one |
| `gh pr ready`, with `--undo` | marks one ready for review, or back to a draft |
| `gh repo view`, `gh auth status`, `gh --version`, `--help` | the repository `stand-in/<folder of the project>`, the account `developer`, and the calls it plays |

What it keeps of a project lives in its git directory, `.git/gh-stand-in/`: `pulls.json`, the pull requests, and `calls.jsonl`, one line per call with its arguments, its standard input when the call reads it, the description it gave, its exit code and what it printed. The git directory, and not a folder next to the bare remote, for three reasons. Every repository has one, with or without a remote, so a call refused for want of a remote is recorded too. It belongs to one project, where several run at the same time in one container. And it is out of the work tree: nothing shows in `git status`, nothing can be committed, and a session that explores the code does not meet it. A `gh pr ready` that is not an `--undo` has `marks_ready` true in its line, whatever became of it: the chain must never make one. A call reads its standard input before it holds that folder, so one `gh` may feed another. `gh_stand_in.calls(project)` and `gh_stand_in.pulls(project)` read both.

A prepared state with a drafted plan holds its draft pull request, as `/surface-plan` leaves it at the first `plan-drafted`: `toy.py` opens it in the stand-in, with the description `surface-status pr-body` prints then, and no call is recorded for it. Without it, `/surface-execute` would find no pull request at any stop and take the path of a branch that has none, the only one the runs took before the stand-in. A state past the approval keeps that first description, since the loop it prepares has not stopped yet, and a stop is what refreshes it.

What the stand-in does not imitate:

- GitHub. There is no network, no account, no CI, no check, no review, no comment and no label, and nothing merges or closes a pull request. The address it prints, `https://github.com/stand-in/<project>/pull/<number>`, leads nowhere.
- The remote. It takes `origin`, wherever it points, for the GitHub repository, and reads the remote-tracking branches of the project, never the remote itself.
- Every other call: `gh api`, `gh pr merge`, `gh pr checks`, `gh issue`, `gh run`, and every flag the table does not name, `--fill`, `--web`, `--repo`, `--template` and `--search` among them. Each gets an error that says the stand-in does not play it, exit code 1, and a line of the record with `played` false, unless it holds `--help`, which prints the calls the stand-in plays whatever the call. `gh pr view` shows no `additions` and no `deletions`, since the stand-in reads no diff. `--jq` is played for paths only, such as `.url` or `.[].headRefName`. `--json` knows the fields the stand-in holds: `number`, `title`, `body`, `state`, `isDraft`, `url`, `headRefName`, `baseRefName`, `author`, `createdAt`, `updatedAt`, and names another as `gh` names an unknown one.
- A terminal. It never prompts, and a usage error is one line, without the usage `gh` prints after it.
- Every wording. The messages of the refusals above are those of `gh`, read in its source or seen on a real repository. The two that are GitHub's own answers to an opening, a branch with nothing to merge and a head the remote does not hold, are written as remembered and were not checked against GitHub.
- Outside a repository, or in one whose git directory cannot be written, it answers `--version` and `--help` only, and records nothing.

Its unit tests, `tests/gh/`, run it as a script in temporary repositories: they are part of the gates, and need neither the container nor a session.

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
| `test_the_nominal_path_reaches_conformant` | `awaiting-approval` | `/surface-execute` | `conformant`, one approval, each slice done once, `conformity.md`, and `shelf/export.py` among the files of the critical zone the description lists. The pull request: its description is the one `surface-status pr-body` prints, set by an edit and no second opening, it is still a draft, and no call marked it ready |
| `test_a_session_killed_in_a_slice_resumes_it` | `awaiting-approval` | `/surface-execute`, killed once an executor has written code, then relaunched | the journal of the killed session kept as is, one approval, each slice done once, `conformant` |
| `test_a_modified_blueprint_stops_the_loop` | `blueprint-modified` | `/surface-execute` | nothing recorded, still `executing`, the final message names the blueprint |
| `test_the_ceiling_hands_back_to_the_developer` | `ceiling` | `/surface-execute` | `blocked` after a second review with findings, and no second fix |

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

The toy shows no branch practice, no pull request and no merge commit, so the session first asks how to name the branch, recommending `feature/<slug>`, and stops. Answer it with `--resume`: it creates the branch, explores and writes `exploration.md`, then opens `interview.md` with the branch question and its answer under "Git", asks its first interview question and stops. Answer it with `--resume` too. Kill the session that takes the answer as soon as the answer is in `interview.md`. Then relaunch without `--resume`, with `/surface-plan` alone:

- it must not explore again, nor ask again a question that has an answer: it asks the next open one;
- answered to the end, it has the plan drafted by the `Plan` agent and writes it as returned, with the three headings the chain reads and the gate of the toy in its `gates` block, has the blueprint drawn and cross-checked, records `plan-drafted`, commits and pushes to the bare remote, then opens a draft pull request in the stand-in `gh`, with the description `surface-status pr-body` prints: from the project, `gh pr view` shows it, and `.git/gh-stand-in/calls.jsonl` holds the calls the sessions made, with no `gh pr ready` among them. The hand over must not say that `gh` is missing.

### An amendment, killed right after it was recorded

```sh
p=$(python3 $toy build awaiting-approval $work/amend)
python3 $toy run $p $work/amend-1.jsonl "/surface-plan Put the year first: year, title, author."
```

Run it in the background and kill it as soon as `journal.jsonl` holds `amendment-received`. Then relaunch with `/surface-plan` alone. The amendment must be under "Amendments" in `interview.md` and in the journal, and revision 2 of `plan.md` and `blueprint.md` must carry it.

### An amendment in the conversation

```sh
p=$(python3 $toy build specs $work/converse)
python3 $toy run $p $work/converse-1.jsonl "/surface-plan Export the shelf as CSV for the bookshop: title, author and year, sorted by author then title."
```

Answer the questions with `--resume` until the session hands over the blueprint and asks: amend, or approve with `/surface-execute`. Answer with `--resume` a question, "why this order?": it is answered and the journal does not move. Then answer "put the year first": it goes under "Amendments" in `interview.md`, the journal holds `amendment-received`, revision 2 is drawn, cross-checked and pushed, and the same question comes back. Answer "fine, go": the journal must hold no `plan-approved`, and the session says that the launch of `/surface-execute` approves.

### A break raised on a commit of the developer, then refused

```sh
p=$(python3 $toy build developer-break $work/break)
python3 $toy run $p $work/break-1.jsonl /surface-execute
```

The review must raise a contract break on the `isbn` column, with a proposal under `plan-changes/`, and the loop hands back in `plan-change-proposed`: the session pushes, presents the proposal and asks accept or decline. Answer with `--resume` that you decline it, and why: the reason goes under "Plan change decisions" in `interview.md`, the journal holds `plan-change-refused`, and the same session goes on: the fix brings the code back to the blueprint, and no later review raises the same break again. Played again with an acceptance instead, the journal holds `plan-change-accepted`, the plan is in `drafting`, and the session tells you to run `/surface-plan`.

### The ceiling, then both ways on

The ceiling test ends on the question: resume, or amend. From the project it leaves blocked, under `/out/basetemp/`, copy the toy folder three times into `$work`. In the first, answer resume with `--resume` on the session of its log: it records `resumed` and goes on with a fresh count in the same session. In the second, relaunch `/surface-execute` in a new session: it records `resumed` too. In the third, give an amendment with `/surface-plan`: it records `amendment-received` and drafts revision 2.
