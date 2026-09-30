# Conformité

Branche relue contre la base `592fcefc4ddd3b3fc983a03846da5f88dd0a3771`, revue `reviews/pass-02.md`, sans constat. `overview.md` est celui approuvé (`alarms` vide). Gates : `gates/run-02.txt`, vert.

## Critères d'acceptation de `overview.md`

1. Une ligne de bilan, sans ligne par fichier.
   - Preuve : `install.py` l. 362 à 386 (`install` renvoie les comptes et l'absence de l'espace de noms avant écriture, l. 377 et 386) et l. 393 à 403 (`summary` : `already up to date`, parties nulles omises, `file` au singulier) ; `run` n'imprime que cette ligne puis les notes (l. 519 à 523).
   - Tests : `tests/install/test_install_from_clone.py` l. 36 (`control-surface installed in <hôte> (8 files written)`, seule ligne), l. 63 (`control-surface updated in <hôte> (1 file written, 1 removed)`), l. 80 (`control-surface updated in <hôte> (1 file removed)`), l. 124 (`already up to date`, seule ligne).
2. Les notes de migration sous la ligne de bilan.
   - Preuve : `install.py` l. 520 à 522 ; `migration_notes` inchangé (l. 315 à 336).
   - Test : `tests/install/test_install_from_clone.py` l. 326.
3. Plus rien sur les permissions ni lien vers le README.
   - Preuve : `PERMISSIONS_HINT` et son commentaire retirés de `install.py` ; aucun appel de `say` ne les porte (l. 510, 513, 520, 522).
   - Test : `tests/install/test_install_from_clone.py` l. 95 (installation avec note de migration, à jour, mise à jour).
4. Sortie du pipe identique à celle d'un clone.
   - Preuve : le même `run` sert les deux chemins (`install.py` l. 544 et 549).
   - Test : `tests/install/test_one_line_install.py` l. 124.
5. Paragraphe Permissions nuancé, texte retenu, sans encadré.
   - Preuve : `README.md` l. 37 à 39, mot pour mot le texte du critère 5 ; relu, aucun test sur la prose (ADR 0032).
6. Ligne d'installation sans renvoi, gardant que l'installateur n'écrit jamais les réglages Claude Code.
   - Preuve : `README.md` l. 9.
7. ADR 0032 allégé, décision de fond intacte ; `ARCHITECTURE.md` sans recommandation de l'auto mode.
   - Preuve : `docs/adr/0032-permissions-left-to-the-mode-no-tests-on-the-readme.md` l. 14, 16 et 18 ; `ARCHITECTURE.md` l. 98, et les invariants l. 57 et 63 inchangés.

Gates : `gates/run-02.txt`, `scripts/gate.sh` vert, format, lint, typage strict, validation des plugins et 1376 tests sur 3.11 puis 3.14.
