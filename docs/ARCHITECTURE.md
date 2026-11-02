# Architecture de Job Tracker Campus

## Parcours personnel

```text
Session Flask / user_loader (compte actif)
  → POST /scan + CSRF
  → owned_jobs.enqueue_user_job(id de session, "scan")
  → jobs SQLite (user_id, état)
  → worker.py : verrou exclusif par base, réservation transactionnelle
  → owned_scanner.scan_user_imap
  → connectors.imap.scan_imap_account (pas de checkpoint direct)
  → owned_importer.import_user_emails (transaction SQLite)
  → owned_imap.save_user_imap_checkpoint (comparaison de la configuration)
  → état succeeded / failed, visible uniquement dans /jobs du propriétaire
```

Le thread HTTP ne réalise pas le scan. Le worker traite un job à la fois. Une panne après l'import mais avant le checkpoint entraîne une relecture ; la déduplication permet cette reprise sans perdre les messages importés.

## Responsabilités

| Module | Responsabilité |
| --- | --- |
| `app/web/__init__.py` | Factory, migrations additives, CSRF et liste des routes personnelles autorisées |
| `app/web/auth.py`, `app/accounts.py` | Session, authentification scrypt, compte actif |
| `app/web/applications.py`, `app/owned_applications.py` | Interface et SQL des candidatures personnelles |
| `app/web/jobs.py`, `app/owned_jobs.py` | Enqueue, liste, réservation, exécution et état des tâches personnelles |
| `app/owned_scanner.py` | Sélection des seuls comptes activés du propriétaire et collecte des résultats |
| `app/connectors/imap.py` | TLS, lecture seule, MIME, détection, UID, lot `ImapScanBatch` |
| `app/connectors/imap_auth.py` | Authentification privée vérifiant propriétaire et identifiant |
| `app/owned_importer.py` | Déduplication, extraction et écritures atomiques par utilisateur |
| `app/owned_imap.py` | Accès aux comptes et sauvegarde conditionnelle du checkpoint |
| `app/oauth_store.py` | Cache privé, remplacement atomique, verrou par compte |
| `app/database.py`, `app/ownership.py` | Schéma SQLite et migrations additives |
| `demo.py`, `app/offline_imap.py` | Lanceur isolé et serveur IMAP en mémoire |

Les modules historiques globaux restent dans le dépôt pour les données et outils existants. Ils ne sont appelés ni par les nouvelles routes de scan ni par le nouveau worker. `app.jobs.init_jobs` reste utilisé pour créer le schéma, sans lancer de job.

## Données et invariants

- `users` : identité, rôle, hash, activation.
- `applications`, `emails`, `imap_accounts`, `jobs` : colonne `user_id`. Les anciennes lignes peuvent conserver `NULL` ; elles ne deviennent pas implicitement la propriété d'un apprenant.
- Les accès personnels qualifient l'identifiant de ressource par `user_id`.
- L'import vérifie le propriétaire actif et effectue ses écritures dans une même transaction `BEGIN IMMEDIATE`.
- Le schéma composite des emails protège `(user_id, message_id)` et la cohérence email/candidature par triggers après migration. La compatibilité avec un ancien schéma ne permet pas de réattribuer implicitement un message.
- Les erreurs d'une boîte n'annulent pas les messages collectés avec succès sur une autre boîte. Le job signale néanmoins un échec partiel.
- Un UID illisible borne le checkpoint avant cet UID ; les messages suivants déjà importés seront ignorés par déduplication à la reprise.
- Sans UIDVALIDITY, l'import reste possible mais aucun checkpoint n'est accepté et le job signale une synchronisation partielle.

## Démonstration

Le lanceur fixe les chemins avant les imports applicatifs. Il utilise une nouvelle base dédiée, remplace le transport IMAP et la lecture du secret système par des objets fictifs, puis interdit les connexions sortantes. Les règles de classification, l'import SQLite, les checkpoints, les sessions et le CSRF restent ceux de l'application.

Le serveur de démonstration utilise le port 5001, un cookie distinct et un worker dans un thread, protégé par un verrou de fichier. Le serveur habituel et son worker sont deux processus distincts sur le port 5000. Les verrous `fcntl` rendent cette version dépendante d'un environnement compatible Unix.
