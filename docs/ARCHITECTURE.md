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

## Routes intégrées

Le registre des routes autorise les scans et la réanalyse des archives, les connecteurs personnels et la liste des jobs. Les opérations du backoffice sont aussi protégées par le rôle administrateur ; elles ne donnent pas accès aux candidatures détaillées d’autrui. Le dashboard ajoute une vue agrégée des apprenants pour l’équipe pédagogique, sans sélectionner les champs personnels des candidatures. Les exports et anciennes actions globales restent bloqués.

La démonstration remplace également l'écriture des secrets et l'authentification IMAP par des simulations, et utilise une détection des fournisseurs sans DNS. Les nouvelles pages ne peuvent donc pas déclencher de stockage dans le keyring réel.

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

## Indicateurs et journal des statuts

`app/dashboard.py` agrège les statuts affichés et les évolutions mensuelles dans une transaction de lecture, avec droits et périmètre promotionnel vérifiés en base. `/dashboard` expose uniquement le rendu chiffré : les apprenants voient leurs indicateurs et l’équipe pédagogique (`admin`) les agrégats des apprenants. La vue personnelle d’un membre de l’équipe reste distincte.

`app/application_history.py`, appelé après la migration de propriété, installe le journal et les triggers de changement du statut effectif. Les anciennes fiches reçoivent un état de départ observé à l’installation ; aucune transition antérieure n’est reconstituée. Les changements sont transactionnels, supprimés avec la candidature et réinitialisés lors d’un transfert de propriétaire. Les premières détections sont agrégées depuis `first_seen` séparément des changements observés.

Le périmètre complet, les filtres et les limites sont documentés dans [DASHBOARD.md](DASHBOARD.md).


## Documents CV/LM et échanges pédagogiques

`app/documents.py` sépare les dossiers de documents (`documents`), leurs versions (`document_versions`) et les commentaires rattachés à chaque version (`document_comments`). Les fichiers restent dans un stockage privé à côté de la base ; leur nom physique est aléatoire et leur intégrité est vérifiée au téléchargement. Les services contrôlent les droits à chaque accès et dans les transactions de mutation.

L’apprenant gère ses fichiers. L’équipe pédagogique (`admin`) peut consulter les dossiers des apprenants et échanger, mais ne remplace ni ne supprime les fichiers. Cet accès documentaire explicite est distinct de l’accès aux candidatures détaillées et aux emails, qui restent personnels. Le dépôt utilise uniquement des traitements locaux ; les formats acceptés sont PDF et DOCX, avec une limite de 10 Mo par fichier.

Le blueprint `/documents` applique les mêmes protections de session et CSRF que les autres modules. La limite multipart de requête est ajustée pour les seules routes de dépôt. Les discussions et versions sont affichées sans exécution de contenu HTML, et les fichiers sont fournis comme pièces jointes. Voir [DOCUMENTS.md](DOCUMENTS.md) pour le périmètre, les limites et la sauvegarde base/fichiers.

### Présentation des emails HTML

Le scan IMAP conserve une alternative HTML de corps dans `DetectedEmail.html_body`, puis `emails.html_body`. Le champ texte existant reste la source de classification et de réanalyse. `app/email_rendering.py` nettoie le HTML à la lecture ; le template l'isole dans une iframe `srcdoc` échappée. Aucun chargement réseau n'est nécessaire pour afficher le corps. Voir [les limites et l'installation](EMAILS_HTML.md).
