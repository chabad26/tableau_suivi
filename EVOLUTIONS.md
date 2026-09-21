# Configuration, réanalyse et travaux en arrière-plan

## Configuration unique

Le fichier `.env` à la racine du projet est chargé au démarrage, même quand une commande est exécutée depuis un autre dossier. Les variables déjà exportées dans le processus ont priorité. Redémarrer Flask **et** le worker après un changement.

[.env.example](.env.example) décrit les clés disponibles. Reporter les clés nécessaires dans le `.env` existant, sans l'écraser :

- `MICROSOFT_CLIENT_ID` : identifiant d'application Microsoft ; le connecteur et le script de diagnostic utilisent désormais la même valeur.
- `MICROSOFT_AUTHORITY` : autorité Microsoft, `common` par défaut.
- `GMAIL_CREDENTIALS_FILE`, `GMAIL_TOKEN_FILE`, `MICROSOFT_TOKEN_CACHE_FILE` : chemins OAuth.
- `DATABASE_PATH` : base SQLite, `data/job_tracker.db` par défaut.
- `SCAN_START_DATE` : date ISO de début des scans, `2026-08-01` par défaut. Une date sans fuseau est interprétée en Europe/Paris ; un offset explicite est accepté. Thunderbird et les API partagent désormais le même instant de départ.
- `FLASK_SECRET_KEY` : clé privée de session. Sans valeur, une clé aléatoire est créée à chaque démarrage ; les sessions précédentes deviennent alors invalides.

Les chemins relatifs partent de la racine du projet. Les répertoires parents des caches OAuth sont créés au besoin. Le `.env` personnel n'a pas été modifié par cette évolution.

## Lancer l'application et le worker

Dans deux terminaux, depuis le projet :

```bash
# Terminal 1 : serveur web
.venv/bin/python web.py
```

```bash
# Terminal 2 : exécution des travaux
.venv/bin/python worker.py
```

Les boutons de scan, réanalyse, test et reconnexion enregistrent une demande puis redirigent immédiatement vers **Travaux en cours** (`/jobs`). Actualiser cette page pour voir le résultat. Sans worker, les demandes restent en attente et sont conservées au redémarrage.

Les instructions OAuth apparaissent dans le terminal du worker ; le navigateur d'authentification peut s'ouvrir sur cette machine. Cette version vise l'utilisation locale Linux et ne fournit pas encore un parcours OAuth pour des utilisateurs distants.

Un verrou de fichier Linux empêche deux workers d'utiliser simultanément la même base. Un seul travail est actif ; les doubles clics sur une même action en attente ou en cours réutilisent la demande existante. Les travaux en attente persistent. Après l'arrêt brutal d'un worker, un travail commencé est marqué en échec au prochain démarrage, sans relance automatique d'une opération potentiellement partiellement exécutée.

Les erreurs affichées ne contiennent pas le texte brut des exceptions OAuth. Un scan ayant échoué sur une source indique un **résultat partiel** et les sources indisponibles. Une reconnexion supprime le cache concerné seulement lorsque son travail est exécuté.

## Réanalyse de toutes les sources

La réanalyse s'appuie sur le sujet, l'expéditeur et le corps archivés dans SQLite pour Thunderbird, Gmail et Microsoft. Elle fonctionne sans connexion aux API et porte sur tous les emails enregistrés, indépendamment de la date de départ des nouveaux scans.

Pour les anciens emails sans corps, une recherche dans les mbox locales peut récupérer le contenu. Il est alors enregistré même si le statut n'a pas changé. Un corps qui ne peut pas être retrouvé est compté comme manquant ; le statut existant n'est pas remplacé à partir de données incomplètes.

Les corrections manuelles et notes sont conservées. La fonction historique de réanalyse mbox reste disponible sous `reclassify_mailboxes()`.

## Suppression et intégrité SQLite

La stratégie est **conserver l'email et mettre `application_id` à `NULL`** quand sa candidature est supprimée. Les messages restent présents pour la déduplication et une réanalyse ultérieure, sans recréer automatiquement une candidature supprimée.

Chaque connexion active `PRAGMA foreign_keys = ON`. L'initialisation détache aussi les références déjà orphelines. Des déclencheurs assurent la même protection pour les anciennes tables qui n'ont pas de contrainte FK déclarée : refus des références invalides à l'insertion/modification et détachement avant suppression. Aucune table n'est reconstruite et aucun email n'est supprimé.

La migration est idempotente et exécutée par les points d'entrée web et worker. La base personnelle n'a pas été ouverte pour les validations ; la réparation de ses éventuelles références orphelines se fera au prochain lancement de l'application. Cette évolution ne crée pas d'isolation par utilisateur : la base, la file et les identifiants OAuth restent partagés dans l'application locale.

## Validation hors ligne

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/ruff check .
.venv/bin/ruff format --check .
npx --yes pyright
```

26 tests couvrent notamment les trois sources, les corps historiques manquants, les corrections manuelles, les anciennes tables sans FK, les orphelins, le chargement `.env` depuis un autre répertoire, la priorité des variables exportées, la file persistante, les interruptions et la disponibilité HTTP pendant un travail bloqué simulé. Aucun accès à une vraie boîte mail ni authentification OAuth réelle n'a été lancé.
