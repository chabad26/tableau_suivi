# 📬 Job Tracker

Job Tracker est une application locale de suivi de candidatures. Elle détecte les emails liés au recrutement, extrait les informations utiles, consolide l'historique d'une candidature et permet de corriger manuellement les résultats lorsque l'automatisation n'est pas suffisante.

> **État présenté : octobre 2026**
>
> Le projet est un prototype fonctionnel en évolution active. L'objectif actuel est de conserver une architecture locale, explicable, testable et indépendante d'un fournisseur de messagerie particulier.

## 🎯 Objectif

Réduire le suivi manuel des candidatures en automatisant les tâches répétitives :

- détecter les emails liés au recrutement ;
- identifier l'entreprise, le poste et la source ;
- déterminer le statut de la candidature ;
- regrouper les messages associés ;
- permettre des corrections et notes manuelles ;
- conserver les données localement dans SQLite ;
- réanalyser les anciens emails quand les règles progressent.

## ✨ Fonctionnalités

### Suivi des candidatures

- création automatique depuis les emails détectés ;
- création manuelle ;
- modification des informations ;
- notes personnelles ;
- suppression et fusion ;
- historique des emails ;
- affichage du contenu des messages ;
- indicateur de complétude ;
- recherche ;
- filtre par statut ;
- filtre par boîte mail ;
- export CSV et Excel avec conservation des filtres actifs.

### Statuts

Les statuts actuellement utilisés sont :

- **Envoyée** ;
- **Reçue** ;
- **Entretien** ;
- **Refus** ;
- **Sans réponse** ;
- **À analyser**.

Le statut **Sans réponse** peut être appliqué automatiquement après une période configurable sans nouvelle activité.

## 📧 Architecture mail unifiée

Les anciens scanners spécifiques Gmail API et Microsoft Graph ont été remplacés par **un scanner IMAP unique**.

- **Gmail** : IMAP + OAuth2/XOAUTH2 ;
- **Microsoft / Outlook / MSN** : IMAP + OAuth2/XOAUTH2 ;
- **Autres fournisseurs IMAP** : authentification adaptée au fournisseur.

Les mots de passe IMAP ne sont pas stockés dans SQLite. Ils sont confiés au gestionnaire de secrets du système via `keyring`.

### Synchronisation incrémentale

Chaque compte conserve son dernier UID traité et son `UIDVALIDITY`. Lorsque la boîte n'a pas changé, le scanner reprend uniquement après le dernier UID connu.

En cas d'échec sur un message, le curseur n'avance pas au-delà du premier UID en erreur afin que le message puisse être retenté lors du scan suivant.

Les messages sont lus avec `BODY.PEEK[]` pour ne pas modifier leur état de lecture.

## 🧱 Architecture actuelle

```text
Comptes email
    ↓
Scanner IMAP unique
    ↓
Classification + Extraction
    ↓
SQLite
    ↓
Worker persistant + Flask/Web UI
```

Le serveur Flask ne réalise pas directement les opérations longues. Les scans, réanalyses et tests de connecteurs sont placés dans une file persistante puis exécutés par `worker.py`.

## 🔄 Flux d'un email

```text
Connexion IMAP
    ↓
Recherche UID incrémentale
    ↓
Lecture sans marquage "lu"
    ↓
Décodage MIME / nettoyage HTML
    ↓
Filtrage
    ↓
Score + statut
    ↓
Extraction entreprise / poste / source
    ↓
Déduplication
    ↓
Création ou mise à jour de la candidature
    ↓
Archivage dans SQLite
```

## 🧩 Responsabilités principales

| Module | Rôle |
| --- | --- |
| `connectors/imap.py` | Connexion, recherche UID, lecture et conversion des messages |
| `connectors/imap_auth.py` | Authentification mot de passe ou OAuth2/XOAUTH2 |
| `connectors/gmail.py` | Gestion des identifiants OAuth Google |
| `connectors/microsoft.py` | Gestion du token OAuth Microsoft |
| `classifier.py` | Score et détection du statut |
| `extractor.py` | Extraction entreprise, poste et source |
| `importer.py` | Orchestration de l'import et déduplication |
| `database.py` | Schéma SQLite et persistance |
| `reclassifier.py` | Réanalyse des emails archivés |
| `jobs.py` | File persistante des travaux |
| `presentation.py` | Préparation des données pour l'interface et les filtres |
| `exports.py` | Structure commune des exports CSV/XLSX |
| `web.py` | Routes Flask et interface |
| `worker.py` | Exécution des tâches en arrière-plan |

## 🛠️ Technologies

- Python 3.14 ;
- Flask ;
- SQLite ;
- IMAP ;
- OAuth 2.0 / XOAUTH2 ;
- Google OAuth ;
- MSAL ;
- keyring ;
- OpenPyXL ;
- HTML / CSS / JavaScript ;
- Ruff ;
- Pyright ;
- unittest.

## 🚀 Installation

```bash
git clone https://github.com/chabad26/tableau_suivi.git
cd tableau_suivi
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copier ensuite les variables nécessaires depuis `.env.example` vers `.env`.

## ▶️ Lancement

Terminal 1 :

```bash
.venv/bin/python web.py
```

Terminal 2 :

```bash
.venv/bin/python worker.py
```

Puis ouvrir :

```text
http://127.0.0.1:5000
```

## 🔐 Confidentialité et sécurité

- SQLite reste local ;
- l'analyse est effectuée localement ;
- les mots de passe IMAP passent par le gestionnaire de secrets système ;
- les jetons OAuth sont stockés localement ;
- Gmail et Microsoft utilisent OAuth2/XOAUTH2 ;
- Gmail sait relancer automatiquement l'autorisation lorsque le refresh token n'est plus utilisable ;
- le projet n'est pas conçu pour être exposé directement comme service multi-utilisateur sur Internet.

## 🧪 Qualité et tests

La suite de tests est organisée par domaine :

```text
test_extractor.py       extraction et HTML
test_imap_connector.py  synchronisation IMAP
test_oauth.py           Gmail / Microsoft OAuth
test_storage.py         SQLite / import / réanalyse
test_jobs.py            file et worker
test_settings.py        configuration
test_web.py             routes / filtres / exports
```

Commandes principales :

```bash
.venv/bin/python -m compileall app tests
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/ruff check .
.venv/bin/ruff format --check .
npx --yes pyright
```

## 📈 Évolution de l'architecture

### Avant

```text
Gmail API ───────┐
Microsoft Graph ─┼─→ pipelines spécifiques
IMAP ────────────┘
```

### Maintenant

```text
Gmail ──────── OAuth2 ──┐
Microsoft ──── OAuth2 ──┼─→ Scanner IMAP commun
Autres mails ─ Password ┘
```

Cette migration a permis de supprimer les scanners API dédiés, réduire les dépendances directes, unifier le traitement des emails et centraliser la synchronisation incrémentale.

Sur le test réel réalisé pendant la migration Gmail, le temps de récupération initial est passé d'un peu plus de deux minutes avec l'ancien chemin à environ trente secondes via IMAP OAuth2.

Les scans suivants utilisent ensuite la synchronisation incrémentale par UID.

## 🗺️ Documentation complémentaire

- [ROADMAP.md](ROADMAP.md)
- [EVOLUTIONS.md](EVOLUTIONS.md)
- [REFACTORING.md](REFACTORING.md)

## ⚠️ Limites actuelles

Le projet reste une application locale en développement. Les axes encore ouverts concernent notamment l'amélioration des règles d'extraction, les statistiques, le durcissement du typage, l'automatisation CI et l'industrialisation du déploiement.

## 📄 Licence

Licence à définir.
