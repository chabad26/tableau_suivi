# Nettoyage du socle Campus — 17 novembre 2026

Le nettoyage est préparé sur `refactor/campus-cleanup`, à partir d'un `main` propre. Il conserve les parcours Campus existants et les scripts de migration. Il ne lance aucun scan réel, ne lit aucun document personnel, ne migre aucun jeton et ne modifie pas la base habituelle.

## Une seule chaîne métier

Le Web et le worker utilisaient déjà les modules `owned_*`, qui contrôlent le propriétaire. Une seconde chaîne mono-utilisateur restait présente et n'était appelée que par ses propres modules historiques et certains tests.

Elle est retirée :

- `app/importer.py`, `app/reclassifier.py` : anciens traitements globaux ; leurs versions personnelles restent dans `owned_importer.py` et `owned_reclassifier.py`.
- `app/connectors/registry.py`, `app/connectors/status.py` : ancien assemblage global des boîtes et des états.
- Les fonctions globales de traitement de `app/jobs.py` : ce module conserve uniquement `init_jobs`, utilisé pour le schéma. L'exécution, la réservation et la récupération restent dans `owned_jobs.py`.
- Les opérations CRUD globales de `app/database.py` : le module conserve les connexions transactionnelles, l'initialisation et les mises à niveau du schéma. Les requêtes métier actives restent dans les modules personnels.
- Les anciens flux OAuth interactifs globaux dans les connecteurs Gmail/Microsoft et leur authentification IMAP partagée. Les flux privés et `authorize_gmail.py` restent disponibles ; aucun nouveau parcours Microsoft n'est ajouté.
- Le modèle `Application` et plusieurs fonctions auxiliaires sans appelant, remplacés depuis longtemps par les lignes SQLite personnelles ou les utilitaires MIME actuels.

La maintenance « Sans réponse » exige désormais un identifiant de propriétaire explicite ; il n'existe plus de mode implicite mettant à jour toutes les candidatures.

## Transport IMAP simplifié

`scan_imap_account(account, since, *, authenticator=...)` exige l'authentificateur fourni par le parcours personnel. Il retourne **toujours `ImapScanBatch`**, avec emails, UIDVALIDITY, UID limite et nombre d'échecs. Les surcharges et options `return_batch` / `persist_sync_state` sont retirées.

Le transport n'importe plus SQLite ni le gestionnaire de secrets et ne sauvegarde jamais un checkpoint. `owned_scanner` collecte les lots ; `owned_jobs` importe d'abord les messages puis demande la sauvegarde conditionnelle du checkpoint. Les tests de transport vérifient les UID proposés et l'absence de modification d'un vrai checkpoint temporaire ; les tests d'intégration vérifient la sauvegarde après import, les échecs et la reprise.

Les anciennes fonctions globales `scan_imap`, `get_imap_accounts` et `test_imap_account` sont supprimées. Les fonctionnalités Web de scan et de test de connexion restent celles du propriétaire connecté.

## Exports, dépendances et outillage

Les exports étaient déjà désactivés. Les URL `/export/csv` et `/export/xlsx` restent indisponibles, sans requête SQL globale ni génération de fichier. `app/exports.py`, l'ancienne implémentation CSV/XLSX, la dépendance `openpyxl` et ses styles inutilisés sont retirés. Les stubs Google API inutilisés sont également retirés des dépendances de développement ; les connecteurs utilisent IMAP et les bibliothèques OAuth actuelles.

`apply_csrf.py`, ancien script de modification automatique du code, est supprimé : le CSRF est déjà installé dans l'application et vérifié par ses tests. Aucune protection CSRF n'est retirée.

Ruff vérifie désormais aussi les imports inutilisés : l'exception globale `F401` est supprimée. La CI lance les tests JavaScript en plus des contrôles Python et traite les avertissements de ressource comme des erreurs. Les déclarations MSAL inutilisées et le style du texte Olidev retiré par l'utilisateur sont nettoyés.

## Compatibilité et données conservées

Les quatre scripts de `migrate/`, les variables de chemins des anciens caches et les anciennes lignes sans propriétaire restent disponibles pour les migrations explicites. Les anciens travaux sans propriétaire restent conservés et ignorés. Aucune table, archive, note, version de document ou cache réel n'est supprimé.

Les anciennes API Python globales ne sont plus disponibles : un script extérieur au dépôt qui les importait devra utiliser un service personnel avec `user_id` ou un outil de migration. Ce nettoyage n'ajoute aucune nouvelle conversion de données au démarrage ; la conversion de `SENT` vers `RECEIVED` existante est conservée.

Les comptes rendus anciens (`REFACTORING.md`, `EVOLUTIONS.md`, `docs/PULL_REQUEST.md`, `docs/VALIDATION.md`) restent comme historique, avec un avertissement vers ce bilan. Le guide de production et les parcours utilisateur actuels restent les références d'exploitation.

## Tests conservés et remplacés

Le point de départ est de **356 tests Python et 9 tests JavaScript**. Les onze tests visant exclusivement les API retirées sont supprimés ou remplacés : deux tests de la file globale, trois du flux OAuth global, cinq de stockage/import/réanalyse/fusion globale et un du scan global sans compte. Les scénarios métier utiles sont couverts par les versions personnelles :

| Scénario | Couverture active |
| --- | --- |
| Déduplication et rollback d'import | `test_owned_importer.py`, `test_sync_integration.py` |
| Réanalyse, corps manquant, notes et statuts manuels | `test_owned_reclassifier.py` |
| File, déduplication, panne et reprise | `test_owned_jobs.py`, `test_worker.py` |
| Anciennes tables, références orphelines, transactions | `test_storage.py`, `test_ownership.py`, tests de migration |
| OAuth privé et identité | `test_owned_oauth.py`, `test_oauth_refresh.py`, `test_oauth_store.py`, `test_authorize_gmail.py` |
| CSRF, routes, accès et statistiques | `test_csrf.py`, `test_web.py`, tests de dashboard |

Deux contrôles sont ajoutés : rejet d'un scan sans authentificateur avant toute connexion et rejet d'une maintenance sans propriétaire valide avant accès SQLite. Les tests du transport vérifient également qu'un changement d'UIDVALIDITY retourne un nouveau curseur sans modifier celui enregistré.

Le faux fichier de test qui imprimait des fournisseurs à l'import sans aucune assertion est supprimé ; les vrais tests de fournisseurs restent dans `test_mail_providers.py` et `test_mx_provider.py`.

## Reproduire les contrôles

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
npx --yes pyright
node --test tests/*.test.cjs
.venv/bin/python -W error::ResourceWarning -m unittest discover -s tests -v
git diff --check
```

Les tests utilisent des bases, caches et documents temporaires et bloquent les connexions réseau. Ils ne prouvent pas la validité actuelle d'un jeton réel ni la configuration du futur hébergeur.

Résultat final : **347 tests Python**, **9 tests JavaScript**, Ruff, formatage, Pyright, compilation Python et contrôle du diff conformes. Les liens locaux des documents modifiés sont vérifiés ; les références aux fichiers retirés sont corrigées ou explicitement signalées comme historiques.
