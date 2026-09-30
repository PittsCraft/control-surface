# Plan : une installation sobre, des permissions nuancées

Révision 1. Instructions d'exécution pour les agents, tranche par tranche. Sources : `specs.md`, `exploration.md`, `interview.md`. Le plan reste vivant : un exécutant qui s'en écarte l'amende dans le commit de son code.

## 1. Objectif et périmètre

L'installateur cesse de lister chaque fichier et de pousser vers les permissions ; le README cesse de recommander l'auto mode sans nuance.

Hors périmètre : le mode `--check` et sa sortie ; les messages d'erreur de l'installateur ; les notes de migration (`note : ...`) ; la détection d'une installation lancée dans le clone de control-surface lui-même (remarque du texte collé dans les spécifications, non demandée) ; les tests de bout en bout ; toute règle de permission livrée ou vérifiée (toujours aucune, ADR 0032).

Critères d'acceptation :

1. Une installation ou une mise à jour réussie imprime une seule ligne de bilan, sans aucune ligne par fichier (Q1) :
   - rien d'installé auparavant dans l'espace de noms : `control-surface installed in <hôte> (<N> files written)` ;
   - une installation existante changée : `control-surface updated in <hôte> (<N> files written, <M> removed)`, chaque partie nulle omise (`(<N> files written)`, `(<M> files removed)`) ;
   - rien à changer : `already up to date`, comme aujourd'hui ;
   - `file` au singulier pour 1.
2. Les notes de migration restent imprimées, sous la ligne de bilan, comme aujourd'hui.
3. L'installateur n'imprime plus rien sur les permissions ni aucun lien vers le README, dans aucun cas (spécifications).
4. La sortie du mode pipe (`curl ... | python3 -`) est identique à celle d'un clone pour le même hôte.
5. La section `### Permissions` du README est le paragraphe de Q2, sans encadré d'avertissement : la boucle avance jusqu'à une commande que les règles ou le mode n'autorisent pas, puis attend ; à vous de choisir : auto mode sur votre machine, `bypassPermissions` seulement dans un conteneur ou une VM jetable, ou le mode par défaut avec vos propres règles allow.
6. La ligne d'installation du README ne renvoie plus à la section Permissions ; elle garde que l'installateur n'écrit jamais les réglages Claude Code.
7. L'ADR 0032 ne décrit plus le texte du README ni un renvoi de l'installateur ; sa décision de fond (aucune règle livrée ni vérifiée, aucun test sur la prose du README) est intacte (Q3). `ARCHITECTURE.md` ne dit plus que le README recommande l'auto mode.

## 2. Décisions d'architecture

- Bilan plutôt que liste (Q1). Écartées : la liste sous `--verbose`, une option que personne ne demande, `git status` montrant déjà les fichiers ; une ligne « Next: /surface-plan », que le README dit déjà.
- « installed » contre « updated » se décide sur l'existence, avant écriture, d'au moins un fichier de l'espace de noms dans l'hôte (`owned_files`), déjà calculée par `install`. Écartée : distinguer par le seul nombre de fichiers écrits, qui confondrait une réparation totale avec une première installation.
- `install` renvoie des comptes structurés au lieu de lignes de texte ; `run` compose la phrase. Précédent : `check` garde ses lignes, inchangé.
- Paragraphe nuancé dans le README (Q2). Écartées : une phrase sans recommandation, qui laisse sans repère sur le danger du bypass hors conteneur ; un tableau, plus long que le sujet.
- ADR 0032 allégé en place (Q3), sans nouvel ADR : le texte du README et la dernière ligne de l'installateur ne sont pas des décisions dures à renverser. Écartés : un ADR 0035 qui remplacerait le 0032 pour un changement de ton ; laisser l'ADR contredit par le dépôt.
- Décisions existantes qui s'appliquent : ADR 0019 (l'installateur n'écrit que son espace de noms, aucun fichier de réglages), ADR 0032 (aucune règle livrée, aucun test sur la prose du README), l'invariant « aucun tiret cadratin ».

## 3. Tranches

<!-- slice:1 -->
### Tranche 1 : une ligne de bilan, plus de renvoi aux permissions

- Objectif : critères 1 à 4.
- Fichiers : `install.py` (`install`, `run`, retrait de `PERMISSIONS_HINT` et de son commentaire) ; `tests/install/test_install_from_clone.py` (assertions l. 55 et 85, nouveaux tests) ; `tests/install/test_one_line_install.py` si une assertion lit la sortie d'installation.
- Précédent : `migration_notes` et les lignes de `check`, pour la forme des messages ; les tests existants de `test_install_from_clone.py`, pour la forme des tests.
- Gates : `scripts/gate.sh`, au premier plan.
- Fini quand : les tests de la section 4 passent, et une installation dans un hôte vide imprime une ligne.
- Dépend de : rien.

<!-- slice:2 -->
### Tranche 2 : README, ARCHITECTURE.md et ADR 0032 nuancés

- Objectif : critères 5 à 7.
- Fichiers : `README.md` (l. 9 et section `### Permissions`), `ARCHITECTURE.md` (section « Permissions and models left to the developer », et l'invariant qui cite l'ADR 0032 si sa formulation le demande), `docs/adr/0032-permissions-left-to-the-mode-no-tests-on-the-readme.md` (paragraphe « Decision »).
- Précédent : le commit `6d40b1f`, qui a écrit ces trois textes.
- Gates : `scripts/gate.sh`, au premier plan.
- Fini quand : aucun des trois fichiers ne recommande l'auto mode seul ni ne mentionne un renvoi de l'installateur ; aucun tiret cadratin.
- Dépend de : la tranche 1, pour que les documents décrivent l'installateur tel qu'il est.

## 4. Tests

Tranche 1, dans `tests/install/test_install_from_clone.py`, avec les aides existantes (`clone`, `git_init`, `run_clone`, `commit_all`) :

- première installation : la sortie est une ligne, `control-surface installed in <hôte> (<N> files written)` avec `N` le nombre de fichiers installés ; aucune ligne `written :` ;
- mise à jour qui écrit et retire : un fichier modifié à la source et un orphelin commités dans l'hôte donnent `control-surface updated in <hôte> (1 file written, 1 removed)` ;
- mise à jour qui retire seulement : `(1 file removed)` ;
- réinstallation : `already up to date`, rien d'autre hors notes ;
- aucun cas n'imprime `permission` ni `github.com` (installation, mise à jour, à jour, avec notes de migration) ;
- les notes de migration suivent la ligne de bilan (le test existant l. 286 reste vert).

Le test existant de `test_one_line_install.py` qui compare la sortie du pipe à celle du clone (l. 114) couvre le critère 4 pour `--check` ; en ajouter un pour l'installation si aucun ne compare déjà les deux sorties d'installation.

Tranche 2 : aucun test sur la prose (ADR 0032). Le contrôle de tiret cadratin des gates couvre les trois fichiers.

## 5. Définition de fini

- `scripts/gate.sh` vert en local, dans l'ordre du CI.
- Un commit par tranche, sujet court en anglais sans préfixe, ni tiret cadratin ni attribution (hook `commit-msg`).
- `ARCHITECTURE.md` à jour dans la même pull request (AGENTS.md).
- Les copies installées non suivies de `.claude/skills/` et `.claude/agents/` restent hors des commits.

## 6. Risques et hypothèses

- Risque : un test hors de `tests/install/` lit la dernière ligne de l'installateur. Vérifié : `tests/ci` et `tests/e2e/toy/toy.py` lancent l'installateur sans lire sa sortie.
- Hypothèse : la forme exacte des phrases de bilan (critère 1), décidée ici ; Q1 a fixé le principe d'une ligne de bilan avec les comptes.
- Hypothèse : le README garde le mot « Permissions » comme titre de section, pour ne pas casser d'éventuels liens entrants vers `#permissions`.
- Hypothèse : la ligne d'installation du README garde « It never writes your Claude Code settings », fait vrai et utile, sans le renvoi.
- Hypothèse : l'ADR 0032 garde son titre, son numéro et sa date ; seul son paragraphe « Decision », et la phrase de « Consequences » s'il le faut, sont allégés.

## 7. Gates

Trouvées dans `CONTRIBUTING.md` et `.github/workflows/ci.yml` : `scripts/gate.sh` les lance toutes, format, lint, typage strict, validation des plugins, tests sur 3.11 puis sur le Python le plus récent. `scripts/gate.sh e2e` reste dehors : facturé, il lance de vraies sessions et demande un jeton et Docker.

```gates
scripts/gate.sh
```
