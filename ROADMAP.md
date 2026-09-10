# 🧭 Roadmap — Job Tracker

## Vision

Job Tracker a pour objectif d'évoluer d'un outil personnel de suivi des candidatures vers une plateforme générique, sécurisée et multi-source, capable de centraliser automatiquement les candidatures issues des emails, des plateformes de recrutement et de Discord.

L'objectif à terme est de proposer une solution utilisable sur **Linux, Windows et Android**, avec des connecteurs modernes vers **Gmail, Outlook / Microsoft 365** et d'autres services.

---

## ✅ MVP actuel

Le prototype actuel permet déjà de :

- scanner les boîtes mail locales Thunderbird ;
- détecter les emails liés à des candidatures ;
- identifier automatiquement l'entreprise, le poste, la source et le statut ;
- distinguer plusieurs états :
  - Proposée ;
  - Envoyée ;
  - Reçue ;
  - Entretien ;
  - Test technique ;
  - Offre ;
  - Refus ;
  - À analyser ;
- corriger manuellement les informations détectées ;
- créer et supprimer une candidature ;
- fusionner des candidatures ;
- consulter l'historique des emails associés ;
- afficher le contenu complet d'un email dans une section dépliable ;
- rechercher et filtrer les candidatures ;
- réanalyser les emails déjà détectés ;
- exporter les données en CSV et Excel ;
- conserver les données dans une base SQLite locale.

---

## 🔧 V0.9 — Fiabilisation du moteur d'extraction

### Objectif

Améliorer la qualité des informations détectées automatiquement.

### Évolutions prévues

- extraction plus fine des intitulés de poste ;
- analyse plus robuste du sujet et du corps des emails ;
- meilleure gestion des formulations inclusives ;
- prise en charge plus large des emails en français et en anglais ;
- meilleure identification de l'entreprise ;
- normalisation des entreprises et des sources ;
- amélioration de la détection des doublons ;
- score de confiance sur les informations extraites ;
- validation humaine lorsqu'une extraction est incertaine.

### Pipeline cible

```text
Sujet du mail
      ↓
Corps texte
      ↓
Structure HTML
      ↓
Métadonnées disponibles
      ↓
Score de confiance
      ↓
Validation utilisateur si nécessaire
```

---

## 📧 V1.0 — Connecteurs email

### Objectif

Ne plus dépendre exclusivement des fichiers locaux de Thunderbird.

### Connecteurs prévus

- Gmail via API Google et OAuth ;
- Outlook / Microsoft 365 via Microsoft Graph ;
- Thunderbird comme connecteur local ;
- possibilité d'ajouter d'autres fournisseurs ultérieurement.

### Architecture cible

```text
Gmail API ──────────┐
                    │
Microsoft Graph ────┼──→ Connecteurs → Moteur d'analyse → Job Tracker
                    │
Thunderbird ────────┘
```

### Points importants

- authentification OAuth ;
- permissions minimales ;
- synchronisation incrémentale ;
- plusieurs comptes possibles ;
- pas de stockage du mot de passe de messagerie ;
- révocation simple des accès.

---

## 🤖 V1.1 — Bot Discord

### Objectif

Récupérer automatiquement les offres d'emploi ou d'alternance proposées dans un salon Discord autorisé.

### Fonctionnement envisagé

```text
Salon Discord autorisé
        ↓
Bot
        ↓
Extraction
Entreprise / Poste / Lien
        ↓
Statut « Proposée »
        ↓
Validation utilisateur
        ↓
Job Tracker
```

### Sécurité

Avant tout déploiement sur un serveur réel, le bot devra être présenté à l'équipe sécurité afin de vérifier :

- les permissions demandées ;
- le périmètre des salons accessibles ;
- l'absence d'accès inutile aux messages privés ;
- la gestion du token ;
- la journalisation ;
- le stockage des données ;
- le comportement du bot en cas d'erreur ;
- la conformité avec les règles internes de l'établissement.

Le bot doit fonctionner avec le **principe du moindre privilège**.

---

## 🔐 V1.2 — Sécurité et confidentialité

### Objectif

Préparer l'utilisation du projet dans un environnement réel.

### Évolutions prévues

- secrets déplacés dans des variables d'environnement ;
- stockage sécurisé des jetons OAuth ;
- gestion des permissions ;
- journalisation des actions importantes ;
- politique de conservation des emails ;
- export des données utilisateur ;
- suppression des données utilisateur ;
- sauvegardes ;
- migrations de base de données ;
- validation et nettoyage des entrées ;
- audit du bot Discord et des connecteurs externes.

---

## 📊 V1.5 — Statistiques et accompagnement

### Objectif

Transformer le tracker en outil de pilotage.

### Indicateurs envisagés

- nombre total de candidatures ;
- répartition par statut ;
- répartition par source ;
- taux de réponse ;
- taux d'entretien ;
- taux de refus ;
- taux d'offre ;
- délai moyen de réponse ;
- candidatures sans réponse ;
- évolution dans le temps ;
- complétude des candidatures ;
- efficacité des différentes sources.

### Funnel envisagé

```text
Proposée
   ↓
Envoyée
   ↓
Reçue
   ↓
Entretien
   ↓
Test
   ↓
Offre
```

Les refus peuvent intervenir à plusieurs étapes du parcours.

---

## 🖥️ V2.0 — Application Desktop

### Objectif

Simplifier le déploiement et l'utilisation sur ordinateur.

### Plateformes

- Linux ;
- Windows.

### Fonctions prévues

- installation simplifiée ;
- assistant de configuration ;
- ajout guidé des comptes email ;
- lancement automatique en arrière-plan ;
- interface locale ;
- mises à jour ;
- sauvegardes ;
- journal de diagnostic.

---

## 📱 V2.5 — Android

### Objectif

Permettre le suivi des candidatures depuis un téléphone.

### Première version envisagée

- consultation des candidatures ;
- modification du statut ;
- ajout de notes ;
- création manuelle ;
- consultation de l'historique ;
- notifications ;
- synchronisation avec le moteur principal.

Dans un premier temps, Android serait principalement un **client de consultation et de suivi**, les connecteurs Gmail et Microsoft restant gérés par le backend ou le moteur principal.

---

## 👥 V3.0 — Version établissement / multi-utilisateur

### Objectif

Faire évoluer Job Tracker vers une solution utilisable par plusieurs apprenants.

### Évolutions prévues

- authentification ;
- comptes utilisateurs ;
- séparation stricte des données ;
- rôles :
  - apprenant ;
  - pédagogue ;
  - administrateur ;
- gestion des promotions ;
- tableau de bord pédagogique ;
- statistiques anonymisées ou agrégées ;
- hébergement maîtrisé ;
- gestion centralisée des connecteurs ;
- conformité RGPD ;
- politique de conservation des données.

---

## 🧠 Évolutions futures

Selon les besoins et les retours utilisateurs :

- analyse sémantique plus avancée ;
- détection automatique de nouvelles plateformes de recrutement ;
- suggestions de relance ;
- rappels ;
- détection des candidatures sans réponse ;
- rapprochement entre offres et candidatures ;
- extraction assistée par IA en option ;
- API publique ;
- plugins ou intégrations supplémentaires.

---

## 🎯 Objectif final

> Passer d'un tracker personnel capable d'analyser Thunderbird à une plateforme indépendante du client mail, connectée à Gmail, Microsoft et Discord, disponible sous Linux, Windows et Android, avec une architecture sécurisée, générique et adaptée à un usage multi-utilisateur.
