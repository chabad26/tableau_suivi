## Évolutions : configuration et scans en arrière-plan

Les scans nécessitent désormais un worker dans un second terminal : `.venv/bin/python worker.py`. Le serveur se lance toujours avec `.venv/bin/python web.py`.

Voir [configuration, lancement et fonctionnement](EVOLUTIONS.md) et [.env.example](.env.example). Les travaux se suivent depuis **Travaux en cours** dans l'interface.

📬 Job Tracker

## État du code au 16 septembre 2026

Le code comporte maintenant des connecteurs IMAP, Gmail et Microsoft. La disponibilité réelle des API dépend de leur configuration et de l'authentification. Les sections historiques ci-dessous sont conservées.

Voir [le bilan de refactorisation](REFACTORING.md) pour les changements effectués, les commandes de vérification et les améliorations encore possibles.

Job Tracker est une application de suivi de candidatures capable d'analyser automatiquement des emails afin d'identifier les entreprises, les postes, les sources et l'avancement des candidatures.

Le projet est actuellement développé comme un prototype local fonctionnel, avec pour objectif d'évoluer vers une solution générique et multi-source utilisable sur Linux, Windows et Android.

✨ Fonctionnalités actuelles

détection des emails liés à une candidature ;

extraction automatique de :

l'entreprise ;

l'intitulé du poste ;

la source ;

l'état de la candidature ;

statuts automatiques :

Envoyée ;

Reçue ;

Entretien ;

Test technique ;

Refus ;

À analyser ;

correction manuelle des informations ;

notes personnelles ;

création manuelle d'une candidature ;

suppression ;

fusion de candidatures ;

recherche et filtres ;

historique des emails ;

affichage dépliable du contenu complet des emails ;

indicateur de complétude ;

réanalyse des emails déjà détectés ;

export CSV ;

export Excel ;

stockage local SQLite.

🧱 Architecture actuelle

Envoyée
   ↓
Reçue
   ↓
Entretien
   ↓
Refus / Sans réponse

Le projet est organisé autour de plusieurs modules indépendants afin de faciliter l'ajout de nouveaux connecteurs à l'avenir.

tableau_suivi/
├── app/
│   ├── connectors/
│   │   ├── gmail.py
│   │   ├── microsoft.py
│   │   ├── imap.py
│   │   ├── registry.py
│   │   └── status.py
│   ├── classifier.py
│   ├── database.py
│   ├── extractor.py
│   ├── importer.py
│   ├── jobs.py
│   ├── maintenance.py
│   ├── presentation.py
│   ├── reclassifier.py
│   ├── settings.py
│   └── statuses.py
├── static/
├── templates/
├── tests/
├── web.py
├── worker.py
├── requirements.txt
└── README.md

🛠️ Technologies

Python ;

Flask ;

SQLite ;

HTML ;

CSS ;

JavaScript ;

🚀 Installation

1. Cloner le projet

git clone <URL_DU_DEPOT>
cd tableau_suivi

2. Créer un environnement virtuel

Sous Linux :

python -m venv .venv
source .venv/bin/activate

Sous Windows :

python -m venv .venv
.venv\Scripts\activate

3. Installer les dépendances

pip install -r requirements.txt

▶️ Utilisation

Lancer l'interface Web

python web.py

Puis ouvrir :

http://127.0.0.1:5000

📊 Interface Web

Le tableau de bord permet de :

consulter toutes les candidatures ;

filtrer par statut ;

rechercher une entreprise ou un poste ;

scanner les nouveaux emails ;

réanalyser les emails existants ;

modifier une candidature ;

ajouter une note ;

créer une candidature manuellement ;

consulter les emails associés ;

afficher le contenu complet d'un email ;

exporter les données en CSV ou Excel.

🧠 Détection automatique

Le moteur analyse actuellement principalement :

le sujet du message ;

le corps du message ;

l'adresse de l'expéditeur ;

le nom affiché de l'expéditeur ;

certaines formulations typiques des plateformes de recrutement.

L'extraction est volontairement basée sur des règles déterministes afin de garder un comportement explicable.

Les règles sont progressivement enrichies afin de prendre en charge :

le français ;

l'anglais ;

les variations de formulation ;

les écritures inclusives ;

plusieurs plateformes ATS et sites d'emploi.

📧 Sources actuellement reconnues

Parmi les sources détectées :

HelloWork ;

LinkedIn ;

Indeed ;

Malt ;

Free-Work ;

Teamtailor ;

Beetween ;

Recruitee ;

iCIMS ;

DigitalRecruiters ;

candidatures directes.

Cette liste est appelée à évoluer.

🔐 Confidentialité

Dans sa version actuelle :

les données restent stockées localement ;

aucune donnée n'est envoyée à un service externe par défaut ;

les emails sont analysés localement ;

SQLite est utilisé pour le stockage.

Les futures intégrations Gmail et Microsoft devront utiliser des mécanismes d'authentification sécurisés, des permissions minimales et une gestion rigoureuse des secrets.

📧 Connecteurs futurs

L'architecture cible prévoit plusieurs sources :

Gmail API ──────────┐
                    │
Microsoft Graph ────┼──→ Connecteurs → Moteur commun → Job Tracker
                    │
IMAP ───────────────┘

🖥️ Plateformes visées

Linux

Plateforme principale actuelle de développement.

Windows

Une version Desktop est prévue avec installation et configuration simplifiées.

Android

Une application mobile est envisagée pour :

consulter les candidatures ;

modifier les statuts ;

ajouter des notes ;

recevoir des notifications ;

consulter l'historique.

🗺️ Roadmap

La feuille de route détaillée est disponible dans :

ROADMAP.md

Les principaux axes sont :

fiabilisation de l'extraction ;

intégration Gmail et Microsoft ;

sécurité ;

statistiques ;

versions Linux et Windows ;

application Android ;

architecture multi-utilisateur.

⚠️ État du projet

Le projet est actuellement en phase de prototype fonctionnel.

Certaines fonctionnalités, notamment les connecteurs Gmail / Microsoft, le multi-utilisateur et Android, font partie de la roadmap et ne sont pas encore disponibles.

🤝 Contributions

Le projet a vocation à être suffisamment générique pour pouvoir évoluer vers un usage plus large.

Les contributions, propositions d'amélioration et retours sur les règles d'extraction seront les bienvenus lorsque le dépôt sera ouvert publiquement.

📄 Licence

Licence à définir.

Une licence open source telle que MIT pourra être retenue pour la publication du projet.
