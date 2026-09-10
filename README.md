# 📬 Job Tracker

Job Tracker est une application de suivi de candidatures capable d'analyser automatiquement des emails afin d'identifier les entreprises, les postes, les sources et l'avancement des candidatures.

Le projet est actuellement développé comme un prototype local fonctionnel, avec pour objectif d'évoluer vers une solution générique et multi-source utilisable sur Linux, Windows et Android.

---

## ✨ Fonctionnalités actuelles

- scan automatique des boîtes mail Thunderbird ;
- détection des emails liés à une candidature ;
- extraction automatique de :
  - l'entreprise ;
  - l'intitulé du poste ;
  - la source ;
  - l'état de la candidature ;
- statuts automatiques :
  - Proposée ;
  - Envoyée ;
  - Reçue ;
  - Entretien ;
  - Test technique ;
  - Offre ;
  - Refus ;
  - À analyser ;
- correction manuelle des informations ;
- notes personnelles ;
- création manuelle d'une candidature ;
- suppression ;
- fusion de candidatures ;
- recherche et filtres ;
- historique des emails ;
- affichage dépliable du contenu complet des emails ;
- indicateur de complétude ;
- réanalyse des emails déjà détectés ;
- export CSV ;
- export Excel ;
- stockage local SQLite.

---

## 🧱 Architecture actuelle

```text
Thunderbird
    ↓
Scanner
    ↓
Classification
    ↓
Extraction
    ↓
SQLite
    ↓
Flask
    ↓
Dashboard Web
```

Le projet est organisé autour de plusieurs modules indépendants afin de faciliter l'ajout de nouveaux connecteurs à l'avenir.

```text
tableau_suivi/
├── app/
│   ├── classifier.py
│   ├── database.py
│   ├── extractor.py
│   ├── importer.py
│   ├── models.py
│   ├── reclassifier.py
│   ├── scanner.py
│   └── statuses.py
├── data/
│   └── job_tracker.db
├── static/
│   └── style.css
├── templates/
│   ├── application.html
│   ├── index.html
│   └── new_application.html
├── main.py
├── show.py
├── edit.py
├── web.py
├── requirements.txt
└── README.md
```

---

## 🛠️ Technologies

- Python ;
- Flask ;
- SQLite ;
- HTML ;
- CSS ;
- JavaScript ;
- OpenPyXL ;
- Thunderbird / mbox.

---

## 🚀 Installation

### 1. Cloner le projet

```bash
git clone <URL_DU_DEPOT>
cd tableau_suivi
```

### 2. Créer un environnement virtuel

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

---

## ▶️ Utilisation

### Scanner les emails depuis le terminal

```bash
python main.py
```

### Réanalyser les emails déjà connus

```bash
python main.py --reclassify
```

### Afficher les candidatures dans le terminal

```bash
python show.py
```

### Lancer l'interface Web

```bash
python web.py
```

Puis ouvrir :

```text
http://127.0.0.1:5000
```

---

## 📊 Interface Web

Le tableau de bord permet de :

- consulter toutes les candidatures ;
- filtrer par statut ;
- rechercher une entreprise ou un poste ;
- scanner les nouveaux emails ;
- réanalyser les emails existants ;
- modifier une candidature ;
- ajouter une note ;
- créer une candidature manuellement ;
- consulter les emails associés ;
- afficher le contenu complet d'un email ;
- exporter les données en CSV ou Excel.

---

## 🧠 Détection automatique

Le moteur analyse actuellement principalement :

- le sujet du message ;
- le corps du message ;
- l'adresse de l'expéditeur ;
- le nom affiché de l'expéditeur ;
- certaines formulations typiques des plateformes de recrutement.

L'extraction est volontairement basée sur des règles déterministes afin de garder un comportement explicable.

Les règles sont progressivement enrichies afin de prendre en charge :

- le français ;
- l'anglais ;
- les variations de formulation ;
- les écritures inclusives ;
- plusieurs plateformes ATS et sites d'emploi.

---

## 📧 Sources actuellement reconnues

Parmi les sources détectées :

- HelloWork ;
- LinkedIn ;
- Indeed ;
- Malt ;
- Free-Work ;
- Teamtailor ;
- Beetween ;
- Recruitee ;
- iCIMS ;
- DigitalRecruiters ;
- candidatures directes.

Cette liste est appelée à évoluer.

---

## 🔐 Confidentialité

Dans sa version actuelle :

- les données restent stockées localement ;
- aucune donnée n'est envoyée à un service externe par défaut ;
- les emails sont analysés localement ;
- SQLite est utilisé pour le stockage.

Les futures intégrations Gmail, Microsoft et Discord devront utiliser des mécanismes d'authentification sécurisés, des permissions minimales et une gestion rigoureuse des secrets.

---

## 🤖 Intégration Discord prévue

Une évolution prévue consiste à connecter Job Tracker à un salon Discord contenant des offres proposées aux apprenants.

Le bot devra pouvoir :

- lire uniquement les salons explicitement autorisés ;
- extraire entreprise, poste, lien et source ;
- créer une candidature avec le statut `PROPOSED` ;
- demander une validation lorsque l'extraction est incertaine.

Avant tout déploiement réel, le bot devra être audité par l'équipe sécurité concernée.

---

## 📧 Connecteurs futurs

L'architecture cible prévoit plusieurs sources :

```text
Gmail API ──────────┐
                    │
Microsoft Graph ────┼──→ Connecteurs → Moteur commun → Job Tracker
                    │
Thunderbird ────────┘
```

L'objectif est que Thunderbird devienne un connecteur parmi d'autres et non une dépendance obligatoire.

---

## 🖥️ Plateformes visées

### Linux

Plateforme principale actuelle de développement.

### Windows

Une version Desktop est prévue avec installation et configuration simplifiées.

### Android

Une application mobile est envisagée pour :

- consulter les candidatures ;
- modifier les statuts ;
- ajouter des notes ;
- recevoir des notifications ;
- consulter l'historique.

---

## 🗺️ Roadmap

La feuille de route détaillée est disponible dans :

```text
ROADMAP.md
```

Les principaux axes sont :

1. fiabilisation de l'extraction ;
2. intégration Gmail et Microsoft ;
3. bot Discord ;
4. sécurité ;
5. statistiques ;
6. versions Linux et Windows ;
7. application Android ;
8. architecture multi-utilisateur.

---

## ⚠️ État du projet

Le projet est actuellement en phase de prototype fonctionnel.

Certaines fonctionnalités, notamment les connecteurs Gmail / Microsoft, Discord, le multi-utilisateur et Android, font partie de la roadmap et ne sont pas encore disponibles.

---

## 🤝 Contributions

Le projet a vocation à être suffisamment générique pour pouvoir évoluer vers un usage plus large.

Les contributions, propositions d'amélioration et retours sur les règles d'extraction seront les bienvenus lorsque le dépôt sera ouvert publiquement.

---

## 📄 Licence

Licence à définir.

Une licence open source telle que **MIT** pourra être retenue pour la publication du projet.
