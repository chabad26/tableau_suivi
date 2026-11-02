# Réanalyser mes emails archivés

Le bouton **Réanalyser mes emails archivés**, sur le tableau des candidatures, relance les règles de classification et d'extraction sur les messages déjà enregistrés dans SQLite. Il ne télécharge aucun email et ne nécessite ni IMAP, ni mot de passe de messagerie, ni autorisation OAuth.

## Utilisation

1. Redémarrer Flask et le worker sur la branche contenant cette évolution, dans deux terminaux :

   ```bash
   .venv/bin/python web.py
   ```

   ```bash
   .venv/bin/python worker.py
   ```

2. Se connecter, ouvrir son tableau et cliquer **Réanalyser mes emails archivés**.
3. La demande est ajoutée à la file personnelle. Une demande identique déjà en attente ou en cours n'est pas ajoutée deux fois. L'interface affiche **Mes travaux**, puis permet d'actualiser le résultat.
4. Revenir au tableau pour consulter les statuts recalculés. Les corrections manuelles conservent la priorité d'affichage.

## Résultat présenté

- **Emails archivés parcourus** : tous les messages archivés du propriétaire.
- **Emails réanalysés** : messages dont le corps archivé n'est pas vide.
- **Statuts modifiés** : statuts d'emails effectivement modifiés par les règles actuelles.
- **Candidatures actualisées** : nombre de candidatures dont les informations automatiques ou la date/statut ont effectivement changé, comptées une seule fois chacune.
- **Emails sans contenu archivé** : messages ignorés faute de corps ; aucune tentative de téléchargement n'est effectuée.

Zéro modification peut être un succès normal si les règles donnent déjà le résultat enregistré.

## Données préservées

- Seuls les emails et candidatures de l'utilisateur de la session sont lus et modifiés. Le `user_id` du formulaire est ignoré.
- Les messages ne sont pas supprimés, fusionnés ou réimportés. Le contenu archivé et les dates de réception restent inchangés. Un message détaché de sa candidature reste détaché.
- Les statuts manuels, notes, marqueurs de correction et détails des candidatures corrigées manuellement sont conservés. Le statut automatique reste recalculable sans remplacer le statut manuel affiché.
- Les informations des candidatures non corrigées manuellement sont réextraites, en conservant la meilleure qualité d'intitulé de poste.
- Le statut automatique vient du message lié le plus récent avec date valide, en comparant les dates en UTC ; à date égale, le message avec le plus grand identifiant SQLite est retenu. Les anciennes dates naïves sont interprétées en UTC. Une date invalide ne détermine pas le statut ni la date de la candidature.
- Les comptes IMAP, caches OAuth et checkpoints ne sont pas utilisés ni modifiés.
- Les anciens messages sans propriétaire restent hors du périmètre, et les anciens jobs sans propriétaire ne sont pas exécutés.

L'ensemble de la réanalyse personnelle s'effectue dans une transaction SQLite : un échec annule les changements du lot et le job est déclaré échoué. La réanalyse utilise les règles actuelles ; leurs limites d'extraction et de classification subsistent.

## Validation

```bash
.venv/bin/python -m unittest tests.test_owned_reclassifier -v
```

La suite utilise une base temporaire et vérifie l'isolation Alice/Bob, les Message-ID identiques entre utilisateurs, les liens historiques incohérents, la conservation des corrections manuelles, la chronologie, les messages incomplets/détachés, l'idempotence, le rollback, le CSRF, l'identité issue de session et la non-exécution des jobs historiques. Un test utilise réellement le classificateur sur un refus fictif ; d'autres injectent des résultats déterministes pour cibler les invariants.

Aucune réanalyse n'est exécutée sur la base réelle pendant cette validation.

## Intitulés présents dans les accusés de candidature

L'extracteur partagé avec l'import reconnaît également un intitulé entre guillemets après « votre candidature est enregistrée », suivi de « pour l’entreprise ». Il reconnaît aussi les récapitulatifs d'envoi dans lesquels le titre terminé par `(H/F)` ou `(F/H)` se situe entre deux occurrences de l'employeur indiqué dans le sujet. La ville, l'employeur répété et le lien vers l'offre sont exclus de l'intitulé.

Un sujet contenant uniquement le nom de l'entreprise ne suffit pas à inventer un poste. Ces nouvelles règles remplissent les titres manquants lors de l'import ou de la réanalyse des candidatures sans correction manuelle ; elles ne remplacent pas les détails des candidatures marquées comme corrigées manuellement.
