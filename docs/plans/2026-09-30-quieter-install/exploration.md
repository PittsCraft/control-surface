# Exploration : une installation sobre, des permissions nuancées

Ce que l'exploration du dépôt a établi, pour qu'une session relancée n'explore pas de nouveau. Ce qui n'est pas listé sous « Lu » n'a pas été lu.

## Règles du dépôt

- Domaine : control-surface est une chaîne de skills et d'agents Claude Code installée dans un projet hôte. Concepts touchés ici : l'installateur (`install.py`), sa sortie, la section Permissions du README, la décision de laisser les permissions au mode (ADR 0032).
- Architecture : `ARCHITECTURE.md`. Invariants qui portent sur la demande : l'installateur n'écrit que dans son espace de noms et ne crée aucun fichier de réglages (ADR 0019) ; la chaîne ne livre ni ne vérifie aucune règle de permission (ADR 0032) ; aucun test n'asserte la prose du README (ADR 0032) ; aucun fichier ne contient de tiret cadratin.
- Artefacts générés : aucun ici. `.claude/skills/surface-*` et `.claude/agents/surface-*.md` du dépôt sont une installation de la chaîne sur elle-même, non suivie par git, jamais éditée à la main.
- Gates : `scripts/gate.sh` (CONTRIBUTING.md, `ci.yml`) les lance toutes : ruff format, ruff check, mypy, pyright, `claude plugin validate` (agents puis skills, sautée sans le CLI), pytest sur 3.11 avec couverture puis sur le Python le plus récent (3.14). `scripts/gate.sh e2e` est facturé, sur demande, dans un conteneur : hors gates.
- Conventions : commits au sujet court en anglais, sans préfixe le plus souvent (`Permissions left to the mode, no tests on the README`), parfois `docs:` ; pull request numérotée dans le sujet au merge (squash). Hook `commit-msg` : ni tiret cadratin ni attribution. Branches : aucune convention écrite ; nom court en kebab-case.
- Décisions : `ARCHITECTURE.md` pour le courant, `docs/adr/` pour les rares décisions dont l'histoire compte ; un ADR remplacé est marqué superseded, sans journal d'amendements (AGENTS.md).
- CI : `.github/workflows/ci.yml` réagit à `pull_request` (opened, synchronize, reopened, ready_for_review) et au push sur `main`. Ses jobs sautent les pull requests en brouillon : un push de branche ou une PR brouillon ne lance rien.

## Ce que la demande touche

- `install.py`, fonction `run` (l. 489-513) : imprime une ligne `written : <chemin>` ou `removed : <chemin>` par fichier changé (`install`, l. 367-390), puis `control-surface installed in <hôte>` ou `already up to date`, les notes de migration, et toujours `PERMISSIONS_HINT` (l. 62-66), y compris quand rien n'a changé. Le mode `--check` imprime une ligne par écart (`drift`, `missing`, `orphan`, `uncommitted`) ou `no drift` ; il n'est pas en cause.
- `README.md` : l. 9 renvoie à la section Permissions (« It never writes your Claude Code settings: [Permissions](#permissions) says how the loop runs unattended ») ; l. 37-40, la section `### Permissions`, un avertissement seul : la boucle s'arrête à chaque commande non permise, lancez-la en auto mode.
- `ARCHITECTURE.md` l. 98 (« the README says to run it in auto mode ») et ADR 0032 (« The README's Permissions section is a warning alone [...] run it in auto mode. The installer [...] ends by pointing at that section. »).
- Précédent : le commit `6d40b1f` (ADR 0032) a créé cet avertissement et ce renvoi ; `bce5bfe` a retiré la création du fichier de réglages à l'installation.
- Tests : `tests/install/test_install_from_clone.py` l. 55 (dernière ligne se termine par `control-surface#permissions`) et l. 85 (renvoi présent même à jour) ; `test_one_line_install.py` compare la sortie du mode pipe à celle du clone et cherche des lignes de `--check`. `tests/ci` et `tests/e2e/toy/toy.py` lancent l'installateur sans lire sa sortie.
- Rien à régénérer.

## Déclarations du projet

`AGENTS.md` : ne jamais utiliser la mémoire native ; lire `ARCHITECTURE.md` d'abord ; un changement d'architecture met à jour `ARCHITECTURE.md` dans la même PR ; un ADR remplacé est marqué superseded ; règles des worktrees. Aucune zone critique déclarée.

## Lu

- `AGENTS.md`, `ARCHITECTURE.md`, `README.md`, `CONTRIBUTING.md`
- `docs/adr/README.md`, `docs/adr/0019-ownership-by-namespace.md`, `docs/adr/0032-permissions-left-to-the-mode-no-tests-on-the-readme.md`
- `.github/workflows/ci.yml`, `scripts/gate.sh`, `.gitignore`
- `install.py` (l. 1-75, 300-395, 460-560)
- `tests/install/test_install_from_clone.py` (l. 1-100), `tests/install/test_one_line_install.py` (l. 100-125)
- recherche de « permission » et « #permissions » dans `skills/`, `agents/`, `tests/prompts/`, `tests/install/`
