quand j'ai installé le skill j'ai eu ce print :
curl -fsSL https://raw.githubusercontent.com/PittsCraft/control-surface/main/install.py | python3 -
written : .claude/skills/surface-execute/SKILL.md
written : .claude/skills/surface-plan/SKILL.md
written : .claude/skills/surface-plan/templates/exploration.md
written : .claude/skills/surface-plan/templates/interview.md
written : .claude/skills/surface-plan/templates/overview.md
written : .claude/skills/surface-plan/templates/plan.md
written : .claude/skills/surface-status/SKILL.md
written : .claude/skills/surface-status/scripts/surface-status
written : .claude/skills/surface-status/scripts/surface_status/__init__.py
written : .claude/skills/surface-status/scripts/surface_status/build.py
written : .claude/skills/surface-status/scripts/surface_status/cli.py
written : .claude/skills/surface-status/scripts/surface_status/events.py
written : .claude/skills/surface-status/scripts/surface_status/gates.py
written : .claude/skills/surface-status/scripts/surface_status/gitops.py
written : .claude/skills/surface-status/scripts/surface_status/guards.py
written : .claude/skills/surface-status/scripts/surface_status/journal.py
written : .claude/skills/surface-status/scripts/surface_status/machine.py
written : .claude/skills/surface-status/scripts/surface_status/plan_folder.py
written : .claude/skills/surface-status/scripts/surface_status/pr_body.py
written : .claude/skills/surface-status/scripts/surface_status/record.py
written : .claude/skills/surface-status/scripts/surface_status/report.py
written : .claude/skills/surface-status/scripts/surface_status/resolve.py
written : .claude/skills/surface-status/scripts/surface_status/settings.py
written : .claude/skills/surface-status/scripts/surface_status/strict_json.py
written : .claude/agents/surface-checker.md
written : .claude/agents/surface-executor.md
written : .claude/agents/surface-extractor.md
written : .claude/agents/surface-reviewer.md
control-surface installed in /path/to/host
Before your first /surface-execute, read how the loop runs unattended: https://github.com/PittsCraft/control-surface#permissions

The installer ran and wrote 28 files, but it wrote them into the control-surface repository itself. They are the untracked .claude/agents/ and .claude/skills/ in your git status. If you meant to try control-surface out on its own repo, that's fine; just keep those two directories out of commits unless you want them there. If you meant to install it in another project, run the command from that project's directory, then delete these two directories here.

Before you run /surface-execute for the first time, the installer asks you to read how the loop runs unattended: https://github.com/PittsCraft/control-surface#permissions

- C'est une très mauvaise UX.
- De plus, l'insistance sur les permissions est à l'opposé de ce qui a été décidé (les devs connaissent le comportement des permissions).
- Enfin dans le README https://github.com/PittsCraft/control-surface#permissions : on recommande le auto mode sans nuance. On pourrait recommander le bypass dans un container ou encore je ne sais quoi d'autre. Nuançons un peu tout en gardant un message court et clair.
