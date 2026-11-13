# Job Tracker Campus

Application locale Python 3.14, Flask et SQLite pour suivre les candidatures des apprenants. Elle analyse les emails, extrait entreprise/poste/source et conserve un historique personnel. Évolutions campus en cours : 12 novembre 2026.

## Administration des comptes

Le backoffice `/admin/users` permet aux administrateurs de créer les comptes apprenants et équipe pédagogique (rôle `admin`), puis de les désactiver/réactiver sans supprimer leurs données. Le lien **Administration** apparaît uniquement pour les administrateurs ; les autorisations sont aussi vérifiées côté serveur.

Pour créer le premier administrateur, utiliser une adresse de connexion encore disponible :

```bash
.venv/bin/python create_account.py admin@campus.invalid --role admin
```

Le mot de passe est demandé sans affichage. Voir [le guide du backoffice](docs/ADMINISTRATION.md).

## Connecteurs personnels (branche Campus)

La page `/connectors` permet de lister, créer, modifier et activer/désactiver les boîtes du compte connecté. Le bouton **Tester la connexion** crée un travail personnel, exécuté par `worker.py`, sans import d'email ni modification du checkpoint. CSRF et contrôles de propriétaire sont conservés.

Gmail et Microsoft nécessitent une autorisation OAuth personnelle déjà configurée : la création du connecteur ne lance pas de consentement OAuth. La réanalyse personnelle des emails archivés est également disponible depuis le tableau, sans accès réseau. Le scan personnel est disponible sur la branche intégrée ; les exports restent désactivés.

Voir [le parcours des connecteurs](docs/CONNECTEURS.md) et [la réanalyse personnelle](docs/REANALYSE.md).

## Installation

```bash
git clone https://github.com/chabad26/tableau_suivi.git
cd tableau_suivi
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

Linux est la plateforme vérifiée : les verrous du worker et d'OAuth utilisent `fcntl`. Node.js/npm est nécessaire pour Pyright. Les dépendances de développement incluent celles de l'application.

## Démonstration hors ligne (pour le jury)

```bash
.venv/bin/python demo.py init
.venv/bin/python demo.py serve
```

Ouvrir **http://127.0.0.1:5001**. L'initialisation demande deux mots de passe fictifs, saisis sans affichage (12 caractères minimum). Comptes : `alice@campus.invalid` et `bob@campus.invalid`.

La base est créée dans `.demo-campus/campus.sqlite3`, indépendamment de `DATABASE_PATH` et de la base habituelle. Un dossier existant est refusé à l'initialisation. Les scans utilisent un serveur IMAP en mémoire et les connexions sortantes sont bloquées. Le serveur lance son propre worker fictif : ne pas lancer `worker.py` pour cette démonstration.

Voir [le scénario de démonstration](docs/DEMO.md).

## Lancement habituel avec des données réelles

Ces commandes concernent la configuration habituelle, contrairement aux commandes de démonstration ci-dessus. Adapter `.env` à partir de `.env.example`, notamment `DATABASE_PATH` et `FLASK_SECRET_KEY` (clé aléatoire persistante, non versionnée).

```bash
.venv/bin/python create_account.py apprenant@example.invalid --role student
```

Le mot de passe est demandé sans affichage et seul son hash scrypt est stocké. Lancer ensuite, dans deux terminaux :

```bash
.venv/bin/python web.py
.venv/bin/python worker.py
```

Interface : **http://127.0.0.1:5000**. Le mode debug est désactivé. Le serveur de développement reste destiné à un usage local. Pour un serveur hébergé, suivre le [guide de déploiement en production](docs/DEPLOIEMENT_PRODUCTION.md).

Le scan suppose que les comptes IMAP personnels et leurs secrets sont déjà configurés depuis les connecteurs. L'autorisation OAuth interactive reste à effectuer séparément. Aucun compte réel ni jeton réel n'est créé ou migré par la démonstration.

À chaque connexion réussie, une réanalyse des archives est mise en file, puis un scan si l'utilisateur possède au moins une boîte activée. Les tâches personnelles déjà en attente ou en cours sont réutilisées. La connexion ne contacte aucun fournisseur mail et les candidatures sont immédiatement accessibles. La réanalyse recalcule également les candidatures « Sans réponse », même si le scan suivant échoue faute de réseau.

Un bandeau suit l'avancement sur les pages authentifiées. Il disparaît quand les tâches réussissent ; le tableau ouvert est alors actualisé. Un échec laisse un message et un lien vers les travaux. Après 30 secondes en file, le bandeau indique l'attente du worker. Après deux minutes, le suivi automatique s'arrête sans bloquer la page ni annuler le travail ; consulter **Mes travaux** pour connaître son état réel. Les erreurs de suivi HTTP arrêtent également l'animation après trois tentatives, chacune limitée à cinq secondes. Sans JavaScript, le lien vers les travaux reste disponible.

Le worker habituel doit rester démarré pour exécuter ces tâches. La démo utilise son worker fictif intégré, y compris pour les mises à jour de connexion. Aucun scan réel n'est lancé par les tests.

## Fonctionnalités disponibles

Le périmètre est le suivi des candidatures réalisées par l’apprenant. La récupération automatique d’annonces et l’envoi de candidatures depuis le site sont abandonnés. Le texte et le lien d’une offre peuvent être conservés manuellement pour faciliter le suivi et la détection du poste.

Le statut « Envoyée » est retiré. Au prochain démarrage, les anciens statuts `SENT` des candidatures et emails deviennent `RECEIVED` (« Reçue »), sans supprimer de données ni modifier les notes ou dates. Les événements historiques bruts sont conservés et leurs chiffres regroupés dans « Reçue ».

- CV et lettres de motivation : dépôt PDF/DOCX privé (10 Mo), versions et échanges apprenant/équipe pédagogique dans l'onglet **CV et lettres**.
- Connexion, déconnexion et comptes actifs : apprenant (`student`) et équipe pédagogique (`admin`). Le rôle historique `trainer` reste lisible en base, mais n’est plus proposé à la création. Aucun rôle ne donne accès aux candidatures détaillées d’autrui.
- Dashboard uniquement chiffré (`/dashboard`) : chiffres personnels des apprenants et agrégats des apprenants par promotion pour l’équipe pédagogique ; historique des changements observés après installation et premières détections présentées séparément.
- Tableau, recherche, filtres, création/modification/suppression et historique des emails propres à l'utilisateur.
- Scan personnel asynchrone : `/scan` → file personnelle → worker → scan IMAP → import SQLite → checkpoint.
- `/jobs` affiche uniquement les travaux de la session, y compris les échecs ; une demande identique en attente/en cours est dédupliquée.
- Gmail et Microsoft : authentification OAuth privée ; OVH, SFR et autres boîtes : IMAP avec secret système. TLS direct ou STARTTLS obligatoire.
- Déduplication des messages, reprise UID/UIDVALIDITY, refus des checkpoints concurrents devenus incohérents.
- Rapprochement des réponses par fil (`In-Reply-To`, `References`) ou expéditeur/sujet précis, y compris sur plusieurs boîtes d’un même utilisateur ; les anciens doublons ne sont pas fusionnés automatiquement.
- Statuts : reçue, entretien, refus, acceptée, sans réponse, à analyser. **Acceptée** est disponible en saisie manuelle ; sa détection automatique n'est pas ajoutée ici.

**Restent désactivés** : exports CSV/XLSX, autorisation/reconnexion OAuth interactive depuis le Web et autres actions globales non migrées. Leurs routes renvoient 503 après authentification. Les anciens jobs sans propriétaire sont conservés et ignorés par le nouveau worker.

## Validation

```bash
.venv/bin/ruff format .
.venv/bin/ruff check .
npx --yes pyright
.venv/bin/python -m unittest discover -s tests -v
```

Les tests d'intégration utilisent une base temporaire et un serveur IMAP fictif ; aucun fournisseur réel n'est sollicité. Ils couvrent les imports atomiques, reprises, doublons, deux utilisateurs, checkpoints concurrents et succès partiels. Des tests de démonstration vérifient aussi qu'une base sentinelle externe reste intacte.

## Données existantes et OAuth

Ne pas lancer de migration sur une base existante sans sauvegarde et vérification préalable. Les scripts historiques restent présents ; ils ne sont pas exécutés automatiquement par cette finalisation.

L'unicité `(user_id, message_id)` possède une migration dédiée (`migrate/migrate_email_uniqueness.py`, à lancer avec `.venv/bin/python -m migrate.migrate_email_uniqueness`). Une base encore en unicité globale refuse un Message-ID déjà détenu par un autre utilisateur plutôt que de fusionner les données. La démonstration initialise uniquement son propre schéma composite.

Les nouveaux caches OAuth sont séparés par **utilisateur et compte**. Les anciens fichiers sont conservés mais ne sont pas automatiquement réutilisés : une migration contrôlée ou une nouvelle autorisation sera nécessaire. Voir [les détails de sécurité](docs/SECURITE.md).

## Documentation

- [Déploiement en production : installation, services, HTTPS, sauvegarde et reprise](docs/DEPLOIEMENT_PRODUCTION.md)

- [Évolutions demandées par le campus et suivi des lots](docs/EVOLUTIONS_CAMPUS.md)
- [Administration des comptes et des promotions](docs/ADMINISTRATION.md)
- [Texte et lien de l'offre dans les candidatures](docs/OFFRES.md)
- [Détection du poste depuis l'offre et les emails](docs/DETECTION_POSTES.md)
- [Dashboard chiffré et limites de l’historique](docs/DASHBOARD.md)
- [CV, lettres, versions et échanges pédagogiques](docs/DOCUMENTS.md)
- [Compte rendu d’intégration et scan réel](docs/INTEGRATION.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Sécurité et limites vérifiées](docs/SECURITE.md)
- [Démonstration pas à pas](docs/DEMO.md)
- [Proposition de pull request](docs/PULL_REQUEST.md)
- Historique : [ROADMAP.md](ROADMAP.md), [EVOLUTIONS.md](EVOLUTIONS.md), [REFACTORING.md](REFACTORING.md).

Licence à définir.

Le [rendu des emails HTML](docs/EMAILS_HTML.md) conserve la mise en forme utile avec nettoyage et isolation du contenu. Après installation des dépendances, redémarrer le serveur web et le worker pour conserver le HTML des prochains messages.

Les [couleurs du Campus](docs/IDENTITE_VISUELLE.md) et leurs variantes pour l'interface sombre sont centralisées dans la feuille de style commune.
