# 📬 Job Tracker

Job Tracker est une application locale de suivi de candidatures qui centralise les informations détectées dans les emails et les saisies manuelles.

Le projet est actuellement en phase de prototype fonctionnel. Son architecture évolue rapidement afin de devenir plus générique, plus robuste et indépendante d’un client mail particulier.

> **État présenté : septembre 2026**
>
> Le projet est en cours d’évolution. Certaines fonctionnalités et choix d’architecture peuvent encore changer à court terme.

## 🎯 Objectif

L’objectif est de réduire le suivi manuel des candidatures en automatisant une partie du travail :

- détecter les emails liés au recrutement ;
- identifier l’entreprise, le poste et la source ;
- suivre l’avancement d’une candidature ;
- centraliser l’historique des emails associés ;
- permettre des corrections manuelles lorsque l’analyse automatique est imparfaite ;
- conserver les données localement dans SQLite.

## ✨ Fonctionnalités actuelles

### Suivi des candidatures

- création automatique à partir des emails détectés ;
- création manuelle ;
- modification des informations ;
- notes personnelles ;
- suppression ;
- fusion de candidatures ;
- recherche et filtrage ;
- historique des emails associés ;
- affichage du contenu des messages ;
- indicateur de complétude ;
- export CSV ;
- export Excel.

### Statuts

Les statuts actuellement utilisés sont :

- **Envoyée** ;
- **Reçue** ;
- **Entretien** ;
- **Refus** ;
- **Sans réponse** ;
- **À analyser**.

Le statut **Sans réponse** peut être appliqué automatiquement après une période configurable sans nouvelle activité.

### Analyse automatique

Le moteur analyse notamment :

- le sujet du message ;
- le corps du message ;
- l’adresse de l’expéditeur ;
- le nom affiché de l’expéditeur ;
- des formulations typiques des plateformes de recrutement.

L’analyse repose actuellement sur des règles déterministes afin de rester explicable et facile à corriger.

Les règles prennent déjà en compte :

- le français ;
- l’anglais ;
- plusieurs formulations de refus, réception et entretien ;
- plusieurs ATS et plateformes d’emploi.

## 📧 Connecteurs email

Trois familles de connecteurs sont actuellement disponibles.

### Gmail

Connexion via :

- Gmail API ;
- OAuth Google.

### Microsoft

Connexion via :

- Microsoft Graph ;
- OAuth Microsoft.

### IMAP générique

Connexion directe aux fournisseurs compatibles IMAP.

Le projet sait notamment détecter automatiquement plusieurs configurations courantes :

- SFR ;
- Orange ;
- Free ;
- La Poste ;
- Infomaniak ;
- OVHcloud.

Plusieurs comptes IMAP peuvent être configurés en parallèle.

Les mots de passe IMAP sont stockés séparément de la base principale via le gestionnaire de secrets système.

## 🧱 Architecture actuelle

```text
Gmail API ───────────┐
                     │
Microsoft Graph ─────┼──→ Connecteurs
                     │
IMAP générique ──────┘
          ↓
    Classification
          ↓
      Extraction
          ↓
        SQLite
          ↓
   File de travaux
          ↓
        Worker
          ↓
        Flask
          ↓
    Dashboard Web
```

Le serveur Web ne réalise pas directement les scans longs.

Les opérations de scan, réanalyse, test de connecteur et reconnexion sont placées dans une file persistante puis exécutées par un worker séparé.

## 🗂️ Structure du projet

```text
tableau_suivi/
├── app/
│   ├── connectors/
│   │   ├── base.py
│   │   ├── common.py
│   │   ├── gmail.py
│   │   ├── imap.py
│   │   ├── microsoft.py
│   │   ├── registry.py
│   │   └── status.py
│   ├── classifier.py
│   ├── database.py
│   ├── exports.py
│   ├── extractor.py
│   ├── importer.py
│   ├── jobs.py
│   ├── mail_filters.py
│   ├── mail_providers.py
│   ├── maintenance.py
│   ├── models.py
│   ├── presentation.py
│   ├── reclassifier.py
│   ├── secrets.py
│   ├── settings.py
│   └── statuses.py
├── static/
├── templates/
├── tests/
├── web.py
├── worker.py
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

## 🛠️ Technologies

- Python ;
- Flask ;
- SQLite ;
- Gmail API ;
- Microsoft Graph ;
- IMAP ;
- OAuth 2.0 ;
- keyring ;
- OpenPyXL ;
- HTML ;
- CSS ;
- JavaScript.

## 🚀 Installation

### 1. Cloner le dépôt

```bash
git clone https://github.com/chabad26/tableau_suivi.git
cd tableau_suivi
```

### 2. Créer l’environnement virtuel

Sous Linux :

```bash
python -m venv .venv
source .venv/bin/activate
```

Sous Windows :

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

Pour les outils de développement :

```bash
pip install -r requirements-dev.txt
```

### 4. Configurer l’environnement

Copier les variables nécessaires depuis `.env.example` vers un fichier `.env`.

Les principales variables sont :

- `MICROSOFT_CLIENT_ID` ;
- `MICROSOFT_AUTHORITY` ;
- `MICROSOFT_TOKEN_CACHE_FILE` ;
- `GMAIL_CREDENTIALS_FILE` ;
- `GMAIL_TOKEN_FILE` ;
- `DATABASE_PATH` ;
- `SCAN_START_DATE` ;
- `FLASK_SECRET_KEY` ;
- `APPLICATION_EXPIRY_DAYS`.

## ▶️ Lancement

Deux processus sont utilisés.

### Terminal 1 : serveur Web

```bash
.venv/bin/python web.py
```

### Terminal 2 : worker

```bash
.venv/bin/python worker.py
```

Puis ouvrir :

```text
http://127.0.0.1:5000
```

## 📊 Interface Web

Le tableau de bord permet actuellement de :

- consulter toutes les candidatures ;
- filtrer par statut ;
- rechercher une entreprise, un poste ou une source ;
- lancer un scan ;
- réanalyser les emails déjà enregistrés ;
- créer une candidature manuelle ;
- corriger une candidature ;
- ajouter une note ;
- consulter l’historique des emails ;
- exporter les données ;
- gérer les connecteurs ;
- suivre l’état des travaux en arrière-plan.

## 🔄 Réanalyse

Les emails détectés sont archivés dans SQLite avec leur sujet, expéditeur et corps.

La réanalyse peut donc fonctionner sans relire les boîtes mail.

Elle permet notamment de profiter des améliorations du moteur de classification sur les messages déjà enregistrés.

Les corrections manuelles restent prioritaires et sont conservées.

## 🔐 Confidentialité

Dans l’état actuel du projet :

- la base SQLite reste locale ;
- l’analyse des emails est effectuée localement ;
- les jetons OAuth sont stockés localement ;
- les mots de passe IMAP ne sont pas enregistrés dans SQLite ;
- les connecteurs utilisent des permissions limitées à la lecture lorsque cela est possible.

Le projet n’est pas encore conçu pour un déploiement multi-utilisateur exposé sur Internet.

## 🧪 Qualité et tests

La suite de tests fonctionne sans accès aux vraies boîtes mail.

Commandes principales :

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/ruff check .
.venv/bin/ruff format --check .
npx --yes pyright
```

Les tests couvrent notamment :

- SQLite ;
- les migrations ;
- la déduplication ;
- les connecteurs simulés ;
- les exports ;
- les routes Flask ;
- la file de travaux ;
- les interruptions du worker ;
- la réanalyse ;
- la conservation des modifications manuelles.

## 📈 Évolution récente

Le projet a récemment évolué d’un scanner fortement lié à une boîte locale vers une architecture multi-connecteur.

Les principaux changements récents sont :

- séparation du moteur de classification ;
- connecteurs Gmail, Microsoft et IMAP ;
- suppression de la dépendance à un client mail local ;
- gestion de plusieurs comptes IMAP ;
- file de travaux persistante ;
- worker séparé ;
- réanalyse basée sur SQLite ;
- amélioration de l’intégrité de la base ;
- simplification des statuts ;
- nettoyage progressif du code historique.

## 🗺️ Roadmap

La feuille de route détaillée est disponible dans [ROADMAP.md](ROADMAP.md).

Les prochains axes concernent notamment :

- la qualité de l’extraction ;
- l’état réel des connexions OAuth ;
- les statistiques ;
- la sécurité ;
- l’industrialisation du projet ;
- les versions Desktop et mobile ;
- une éventuelle architecture multi-utilisateur.

## ⚠️ État du projet

Job Tracker reste un prototype actif.

Le dépôt évolue rapidement et certaines parties de l’interface, du modèle de données ou de l’architecture peuvent encore être modifiées.

## 📄 Licence

Licence à définir.
