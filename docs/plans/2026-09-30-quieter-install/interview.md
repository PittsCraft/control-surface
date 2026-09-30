# Interview : une installation sobre, des permissions nuancées

Questions, réponses et amendements du plan, écrits au fil de l'eau. Une question est écrite ici avant d'être posée, sa réponse dès qu'elle est donnée : une session relancée reprend à la première question sans réponse et n'en repose jamais une. Les dates sont celles des réponses.

## Questions

### Q1. Que doit imprimer une installation ou une mise à jour réussie ?

Aujourd'hui : une ligne `written :` ou `removed :` par fichier (28 à la première installation), puis `control-surface installed in <hôte>` ou `already up to date`, les notes de migration, et toujours le renvoi vers `#permissions`. Le renvoi disparaît dans tous les cas (spécifications). `--check` et les messages d'erreur ne changent pas.

Options :
- A. Une seule ligne de bilan : `control-surface installed in <hôte> (28 files written)`, ou `updated in <hôte> (3 written, 1 removed)`, ou `already up to date` ; les notes de migration restent, sous le bilan.
- B. Comme A, plus une ligne sur la suite : `Next: /surface-plan <your need>` dans une session Claude Code du projet.
- C. La liste par fichier gardée derrière une option `--verbose`, le bilan seul par défaut.

Recommandé : A, le bilan dit tout ce qui sert et le README dit déjà la suite ; C ajoute une option que personne ne demande (`git status` montre les fichiers).

Réponse (2026-09-30) : « A. Bilan seul (Recommandé) »

### Q2. Que dit la section Permissions du README ?

Aujourd'hui, un encadré `[!WARNING]` : la boucle s'arrête à chaque commande non permise, lancez-la en auto mode. Les spécifications demandent de nuancer, court et clair.

Options :
- A. Un paragraphe sans encadré, qui constate puis laisse choisir : « The loop runs until a command needs an approval your rules or mode do not give, then waits for you. How much it does alone is your call: auto mode on your machine, `bypassPermissions` only in a container or a VM you can throw away, or the default mode with your own allow rules. »
- B. Une phrase, sans aucune recommandation : « The loop runs within your permission mode and rules, and waits at any command they do not allow. »
- C. Le constat, puis un petit tableau mode / où / ce qu'il coûte.

Recommandé : A, il nuance sans insister, et le mot sur le conteneur protège d'un bypass sur la machine du développeur ; C est plus long que le sujet ne mérite.

Réponse (2026-09-30) : « A. Paragraphe nuancé (Recommandé) », avec le texte proposé.

### Q3. Que devient l'ADR 0032, dont la décision dit « run it in auto mode » et « the installer ends by pointing at that section » ?

Le fond de l'ADR tient : la chaîne ne livre ni ne vérifie aucune règle, aucun test sur la prose du README. Seuls ces deux détails changent. AGENTS.md : un ADR remplacé est marqué superseded, sans journal d'amendements.

Options :
- A. Retirer de l'ADR 0032 les deux détails (texte du README, renvoi de l'installateur), qui ne sont pas des décisions dures à renverser ; `ARCHITECTURE.md` porte le reste. Git garde l'histoire.
- B. Un ADR 0035 qui remplace le 0032, marqué superseded, et redit la décision entière avec la nouvelle nuance.
- C. Laisser l'ADR tel quel, ne changer que `ARCHITECTURE.md`.

Recommandé : A, un nouvel ADR pour un changement de ton serait disproportionné, et C laisserait un ADR contredit par le dépôt.

Réponse (2026-09-30) : « A. Retirer les détails (Recommandé) »
