# End to end tests

The chain run for real, headless, on a toy project: does a session driven by the prompts do what the README promises? The strategy, and why the sessions bypass permissions in a container, is in `docs/adr/0025-end-to-end-on-a-toy-project.md`.

Every scenario is billed and takes minutes: run them on demand, before a release or after a change of the prompts, never in CI.

## What you need

- Docker. The sessions bypass permissions, which is not safe on your machine: a command could reach outside the toy folder. They run in the container of `tests/e2e/Dockerfile`, which holds Python 3.11, git, the `claude` CLI, pytest and a stand-in for `gh`, under a user that is not root. `toy.py` refuses to start a session anywhere else.
- A token in your environment: `CLAUDE_CODE_OAUTH_TOKEN`, printed by `claude setup-token`, or `ANTHROPIC_API_KEY`. The container cannot use the login of your `claude` on the host, which macOS keeps in its keychain. The token is passed to `docker run` from your environment and never written in the image. Sessions use its account.

## The toy project

`toy/toy.py build <state> <dest>` makes `<dest>/shelf`, a git repository holding a small module (`shelf`, a list of books read from a JSON Lines file), its tests, an `AGENTS.md` that declares the CSV export a critical zone, and a gate command, `python3 -m unittest discover -s tests -q`, with `<dest>/origin.git` as its bare remote. It installs the chain from this clone, then drives one plan folder, `docs/plans/<date>-csv-export/`, to the state asked for, recording each event through the installed state script. It prints the path of the project.

The states, from the need to the review:

| State | What the project holds |
|---|---|
| `specs` | the main branch, the chain installed, no plan |
| `specs-ci` | the same, with a CI workflow that runs the gate on every push, of any branch, and on every pull request |
| `plan-written` | the branch `feat/csv-export`, the interview closed and `plan.md` written, no blueprint yet. Nothing of the plan folder is committed |
| `blueprint-drawn` | the same, with `blueprint.md` drawn and not cross-checked yet |
| `planning-ceiling` | specs that ask to rewrite the shelf file once the CSV is printed, a plan that does it, a blueprint that says the file is never written, and two cross-checks that count that omission, `max_autonomous_passes: 1`. Nothing committed |
| `awaiting-approval` | the branch `feat/csv-export`, a plan drafted at revision 1 (two slices), pushed, and its draft pull request, open in the stand-in `gh` |
| `unpushed` | that plan drafted and committed, the branch never pushed, no pull request |
| `unpushed-ci` | the same, under the CI of `specs-ci`, which `exploration.md` names |
| `two-plans` | a second plan, `<date>-count-books`, drafted on the same branch: both await their approval |
| `slice-uncommitted` | revision 1 approved, the work of slice 1 written and `slice-done` recorded, neither committed |
| `blueprint-modified` | revision 1 approved, slice 1 done, then a commit of the developer that edits `blueprint.md` |
| `developer-break` | both slices done, then a commit of the developer that adds an `isbn` column the blueprint leaves out |
| `plan-change-proposed` | that commit raised as a contract break by a review, with its proposal under `plan-changes/`, committed and not pushed |
| `fixing` | both slices done with a defect the tests do not see (lines sorted by title only), and the review that found it: a fix is due |
| `ceiling` | that defect and that review, then a fix that missed it, `max_autonomous_passes: 1` |
| `blocked` | the same, then a second review that finds the defect again, and `blocked`, pushed |
| `done`, `defect`, `deviation` | both slices done and nothing reviewed yet: as planned, with that same defect, or with the tests of slice 1 in another file than the plan names. The evaluations review them (`evals/README.md`) |
| `slow-gate` | `done`, with a test on the main branch that sleeps 20 seconds, so that the gate lasts |
| `review-unrecorded` | `done`, the gates run green and committed, then a clean review and `conformity.md` written, neither recorded nor committed |

A state named after a death, `plan-written`, `slice-uncommitted` or `review-unrecorded`, holds what a session leaves when it dies at that point: the files are the whole state of a plan, so a state built there is the one a kill would leave, without the luck a kill needs to fall between a record and its commit.

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

A prepared state with a drafted plan holds its draft pull request, as `/surface-plan` leaves it at the first `plan-drafted`: `toy.py` opens it in the stand-in, with the description `surface-status pr-body` prints then, and no call is recorded for it. Without it, `/surface-execute` would find no pull request at any stop and take the path of a branch that has none, the only one the runs took before the stand-in. A state past the approval keeps that first description, since the loop it prepares has not stopped yet, and a stop is what refreshes it. The states never pushed, `unpushed` and `unpushed-ci`, have none: the push and the opening are what their scenarios wait for.

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

A scenario asserts what the project holds once its sessions ended: the journal, the files of the plan folder, what git committed and what the bare remote holds, the record of the stand-in `gh`. Of what a session says it holds one word at most, such as the command it must name. A model may take another valid path from one run to the next: read the logs before blaming the chain.

### The developer's answers

Some scenarios need the developer's answers. No model plays the developer here: that is what the evaluations do (`evals/README.md`). Each answer is written in the test and given in a session of its own, which `--resume` ties to the conversation. Every question of the chain is lettered and carries a recommendation, so one reply, "I take the option you recommend.", answers any question of an interview, whatever the session asked. Where the scenario turns on what is said, the reply is its own: an amendment, a refusal with its reason, "Fine, go.".

### Killed sessions

A scenario kills a session at a moment it reads in the files of the project or in the stream of the session: its process group first, then whatever it left at work in the project, since a gate runs in a process group of its own and would go on to record its run while the next session works. The relaunch is a fresh session, without `--resume`. Where the moment is too short to hit, between a record and its commit or between a commit and its push, the scenario starts from a prepared state that holds what a death there leaves.

### The loop

| Test | Start | Sessions | What must hold |
|---|---|---|---|
| `test_the_nominal_path_reaches_conformant` | `awaiting-approval` | `/surface-execute` | `conformant`, one approval, each slice done once, `conformity.md`, and `shelf/export.py` among the files of the critical zone the description lists. The pull request: its description is the one `surface-status pr-body` prints, set by an edit and no second opening, it is still a draft, and no call marked it ready |
| `test_a_session_killed_in_a_slice_resumes_it` | `awaiting-approval` | `/surface-execute`, killed once an executor has written code, then relaunched | the journal of the killed session kept as is, one approval, each slice done once, `conformant` |
| `test_a_modified_blueprint_stops_the_loop` | `blueprint-modified` | `/surface-execute` | nothing recorded, still `executing`, the final message names the blueprint |
| `test_the_ceiling_hands_back_to_the_developer` | `ceiling` | `/surface-execute` | `blocked` after a second review with findings, and no second fix |

### Planning with the developer

| Test | Start | Sessions | What must hold |
|---|---|---|---|
| `test_planning_killed_in_the_interview_resumes_at_the_next_question` | `specs` | `/surface-plan` with the need; the session that takes the first answer of the interview killed once `interview.md` holds it; then `/surface-plan` alone, and the recommendation at every question | the journal of the killed session kept as is, `exploration.md` untouched, no question that had its answer written a second time, one `plan-drafted` with the gate of the toy, the plan committed and pushed, and one draft pull request with the description `surface-status pr-body` prints |
| `test_an_amendment_killed_once_recorded_is_drafted_at_the_relaunch` | `awaiting-approval` | `/surface-plan` with an amendment, killed once the journal holds `amendment-received`, then `/surface-plan` alone | the amendment in `interview.md` at the kill, one `amendment-received`, revision 2 of the plan and of the blueprint with the header in its new order, pushed, the description refreshed and no second opening |
| `test_a_conversation_after_the_hand_over_amends_and_approves_nothing` | `awaiting-approval` | `/surface-plan`, then in its conversation a question, an amendment and "Fine, go." | the question records nothing. The amendment is in `interview.md` and in the journal, revision 2 is drafted and pushed. The sentence that agrees records nothing, and the session names `/surface-execute` |

### The developer's turn in the loop

| Test | Start | Sessions | What must hold |
|---|---|---|---|
| `test_a_break_on_a_commit_of_the_developer_is_raised_then_refused` | `developer-break` | `/surface-execute`, then the refusal with its reason | a review with a break and its proposal, `plan-change-proposed`, the branch pushed and the description refreshed. Then one `plan-change-refused`, the reason in `interview.md`, no later review with a break, `conformant`, and an export back to its three columns |
| `test_an_accepted_plan_change_goes_back_to_planning` | `plan-change-proposed` | `/surface-execute`, then the acceptance | the first session records nothing, pushes the commit the state left unpushed and refreshes the description. Then `plan-change-accepted`, `drafting`, the decision in `interview.md`, committed and pushed, and the session names `/surface-plan` |
| `test_a_resumption_in_the_session_goes_on_past_the_ceiling` | `ceiling` | `/surface-execute`, then "Resume." | `blocked`, then `resumed` right after it and once, a gate run after it, and `conformant` or `blocked` again |
| `test_a_relaunch_resumes_a_plan_blocked_at_the_ceiling` | `blocked` | `/surface-execute` | the same, in a fresh session |
| `test_an_amendment_takes_a_plan_blocked_at_the_ceiling_back_to_planning` | `blocked` | `/surface-plan` with an amendment | `amendment-received` right after `blocked`, no approval, revision 2 drafted with slices 1 and 2 kept, pushed, the description refreshed |

### The status command, and a branch with two plans

| Test | Start | Sessions | What must hold |
|---|---|---|---|
| `test_an_abandon_waits_for_a_yes_then_fails_the_conformity_check` | `done` | `/surface-status abandon`, then the yes with its reason | nothing recorded before the yes. Then `abandoned` with the reason, the journal committed and pushed, the description refreshed, and `surface-status check --require conformant` exits with 1 on `abandoned-after-approval`, since the plan was approved |
| `test_two_plans_on_a_branch_are_put_to_the_developer` | `two-plans` | `/surface-plan`, `/surface-execute` or `/surface-status abandon`, one test each | nothing recorded in either plan, nothing changed in the working tree, and the final message names both plans |

### Without a session

`test_a_prepared_state_is_the_one_named` and its two neighbours build each state, `test_a_session_bypasses_permissions_in_the_container_only` checks the command line of a session and its refusal outside the container, and `test_a_kill_takes_what_a_session_left_at_work` kills a process started in a group of its own. They cost nothing, and run without a token:

```sh
scripts/gate.sh e2e -k "prepared or bypasses or left_at_work"
```

## Playing a scenario by hand

To look into a scenario that failed, or to play a path no test covers yet, run the sessions yourself, one session per answer: `run` prints the session id, and `--resume <session id>` gives the next answer to the same conversation. A fresh session, without `--resume`, is how a relaunch after a dead session is tested. To kill a session mid-way, run it in the background and kill its process group (`kill -9 -<pid>`), watching the plan folder to choose the moment.

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

In the container, with `toy=tests/e2e/toy/toy.py` and a scratch folder `work=/out/manual`:

```sh
p=$(python3 $toy build awaiting-approval $work/amend)
python3 $toy run $p $work/amend-1.jsonl "/surface-plan Put the year first: year, title, author."
python3 $toy run $p $work/amend-2.jsonl "I take the option you recommend." --resume <session id>
```
