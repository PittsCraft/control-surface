# Revue, passe 02

Branche relue contre la base `592fcefc4ddd3b3fc983a03846da5f88dd0a3771`, commits du plan `9c24e28`, `5babeb1`, `9cb48f3`, `e42c6c0`, `5d4bde6`, `8dcfeed`, `d2d5542`, et le commit du développeur `c358430` (l'accord de push ajouté à `interview.md`, sans effet sur le contrat). `overview.md` est celui approuvé : `alarms` vide. Gates : `gates/run-02.txt`, vert (1376 tests, sur 3.11 puis 3.14). Le correctif de la passe 01 (`d2d5542`) ne change que de la prose (README et documents du plan), qu'aucun test ne lit hors du contrôle de tiret cadratin ; le diff de la branche n'ajoute aucun tiret cadratin.

## Contrôle des amendements

Toujours un seul amendement depuis l'approbation (journal, ligne 6 ; commit `9cb48f3`) : dans la section 2 de `plan.md`, un numéro d'ADR donné d'avance à une alternative écartée devient « un nouvel ADR ». Il ne touche ni les données, ni les frontières, ni le comportement visible, ni une zone critique : `overview.md` reste vrai. Aucun autre changement de `plan.md` depuis `5babeb1`.

## Suite du constat de la passe 01

Le défaut 1 est corrigé : `README.md` l. 39 porte, mot pour mot, le texte retenu du critère 5 de `overview.md` (l. 19), sans la commande ajoutée ni encadré d'avertissement ; le titre `### Permissions` est gardé (l. 37).

## Constats

Aucun.

## Points vérifiés sans constat

- Critère 1 : `install.py` l. 362 à 386, `install` renvoie `(écrits, retirés, préexistant)`, l'espace de noms étant lu avant toute écriture (l. 377) et `fresh` valant `not owned` (l. 386) ; `summary` l. 393 à 403 rend `already up to date`, omet chaque partie nulle et met `file` au singulier. Tests : `tests/install/test_install_from_clone.py` l. 36 (sortie exacte d'une première installation, une ligne), l. 63 (`1 file written, 1 removed`), l. 80 (`1 file removed`), l. 124 (sortie exacte `already up to date`).
- Critère 2 : `install.py` l. 520 à 522, la ligne de bilan puis les notes ; test l. 326.
- Critère 3 : `PERMISSIONS_HINT` et son commentaire retirés, `run` ne dit plus que le bilan et les notes (l. 519 à 523) ; test l. 95 (installation avec note, à jour, mise à jour : ni `permission` ni `github.com`).
- Critère 4 : même `run` pour le clone et le pipe (`install.py` l. 544 et 549) ; test `tests/install/test_one_line_install.py` l. 124, sorties comparées en entier.
- Critère 6 : `README.md` l. 9.
- Critère 7 : `docs/adr/0032-permissions-left-to-the-mode-no-tests-on-the-readme.md` l. 14, titre, numéro et date gardés, « Consequences » inchangé et toujours vrai ; `ARCHITECTURE.md` l. 98.
- Hors périmètre respecté : `check` et sa sortie inchangés (`install.py` l. 504 à 514), messages d'erreur et notes de migration inchangés, aucun fichier de réglages créé (ADR 0019).
- Aucune référence restante à `written :`, `removed :`, `PERMISSIONS_HINT` ou `#permissions` hors des documents du plan.
- Les copies non suivies de `.claude/skills/` et `.claude/agents/` sont hors des commits (`git status`).

## Comptes

Défauts : 0. Écarts : 0. Ruptures : 0.
