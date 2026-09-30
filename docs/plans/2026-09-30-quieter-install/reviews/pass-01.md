# Revue, passe 01

Branche relue contre la base `592fcefc4ddd3b3fc983a03846da5f88dd0a3771`, commits du plan `9c24e28`, `5babeb1`, `9cb48f3`, `e42c6c0`, `5d4bde6`, et le commit du développeur `c358430` (une réponse ajoutée à `interview.md`, sans effet sur le contrat). `overview.md` est celui approuvé : `alarms` vide. Gates : `gates/run-01.txt`, vert (1376 tests, sur 3.11 puis 3.14).

## Contrôle des amendements

Un seul amendement depuis l'approbation (journal, ligne 6 ; commit `9cb48f3`) : dans la section 2 de `plan.md`, « un ADR 0035 » devient « un nouvel ADR », pour une alternative écartée. Il ne touche ni les données, ni les frontières, ni le comportement visible : `overview.md` reste vrai.

## Constats

### 1. Défaut : le paragraphe Permissions du README n'est pas le texte retenu

- Preuve : `overview.md`, critère 5 (l. 19), fixe le texte retenu, celui de l'option A de Q2 que le développeur a choisie « avec le texte proposé » (`interview.md` l. 25 et 31) : « The loop runs until a command needs an approval your rules or mode do not give, then waits for you. How much it does alone is your call: auto mode on your machine, `bypassPermissions` only in a container or a VM you can throw away, or the default mode with your own allow rules. » `README.md` l. 39 porte un autre texte : « The loop advances until it reaches a command your rules or mode do not allow, then waits for you. The choice is yours: auto mode (`claude --permission-mode auto`) on your own machine, `bypassPermissions` only in a disposable container or VM, or the default mode with your own allow rules. » Le sens est proche, mais les mots diffèrent et une commande `claude --permission-mode auto` a été ajoutée. La zone sensible 3 de `overview.md` (l. 116) rappelle que cette phrase n'est protégée que par la relecture.
- Correction : remplacer `README.md` l. 39 par le texte retenu du critère 5, mot pour mot, sans la commande ajoutée. Aucun test (ADR 0032).

## Points vérifiés sans constat

- Critère 1 : `install.py` l. 362 à 403 ; `install` renvoie `(écrits, retirés, préexistant)`, l'existence de l'espace de noms étant lue avant écriture (l. 377, 386) ; `summary` omet chaque partie nulle et met `file` au singulier. Tests `tests/install/test_install_from_clone.py` l. 55, 75, 90, 136.
- Critère 2 : `install.py` l. 520 à 522, la ligne de bilan puis les notes ; test l. 326.
- Critère 3 : `PERMISSIONS_HINT` retiré ; test l. 95 (installation avec note de migration, à jour, mise à jour).
- Critère 4 : même `run` pour le clone et le pipe (`install.py` l. 544 et 549) ; test `tests/install/test_one_line_install.py` l. 124.
- Critère 6 : `README.md` l. 9.
- Critère 7 : `docs/adr/0032-permissions-left-to-the-mode-no-tests-on-the-readme.md` l. 14 ; `ARCHITECTURE.md` l. 98.
- Les copies non suivies de `.claude/skills/` et `.claude/agents/` sont hors des commits.

## Comptes

Défauts : 1. Écarts : 0. Ruptures : 0.
