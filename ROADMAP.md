# 🧭 Roadmap — Job Tracker

## Vision

Job Tracker doit évoluer d’un outil personnel de suivi de candidatures vers une application générique, sécurisée et multi-source.

L’objectif est de centraliser automatiquement les candidatures détectées dans les emails, tout en conservant la possibilité de corriger et enrichir les informations manuellement.

> **Cette roadmap reflète l’état du projet en septembre 2026.**
>
> Le projet évolue rapidement. Les priorités peuvent changer selon les retours d’usage et les besoins identifiés pendant le développement.

---

## ✅ État actuel du prototype

Le socle fonctionnel comprend déjà :

- un dashboard Web Flask ;
- une base SQLite locale ;
- la création automatique et manuelle de candidatures ;
- la modification et la suppression ;
- la fusion de doublons ;
- la recherche et les filtres ;
- l’historique des emails ;
- les exports CSV et Excel ;
- la réanalyse des emails déjà enregistrés ;
- une file de travaux persistante ;
- un worker séparé du serveur Web ;
- Gmail via API Google ;
- Microsoft via Graph ;
- IMAP générique multi-compte ;
- la détection de plusieurs fournisseurs IMAP ;
- le suivi de l’état des comptes IMAP ;
- la conservation des corrections manuelles.

### Statuts actuels

```text
Envoyée
   ↓
Reçue
   ↓
Entretien
   ↓
Refus / Sans réponse

À analyser
```

Le statut **Sans réponse** est appliqué automatiquement après une durée configurable sans nouvelle activité.

---

## ✅ Refactorisation du socle

Plusieurs travaux initialement prévus dans la roadmap sont désormais réalisés :

- séparation du moteur de classification ;
- centralisation de la configuration ;
- architecture de connecteurs commune ;
- suppression de la dépendance à un client mail local ;
- connecteurs Gmail, Microsoft et IMAP ;
- réanalyse à partir des données SQLite ;
- travaux exécutés hors des requêtes HTTP ;
- persistance des travaux ;
- intégrité renforcée des relations SQLite ;
- stockage séparé des secrets IMAP ;
- simplification des statuts ;
- nettoyage du code historique ;
- tests hors ligne des composants principaux.

---

## 🔧 Prochaine étape — Fiabilisation du moteur

### Objectif

Améliorer la qualité des informations détectées automatiquement.

### Travaux envisagés

- améliorer l’extraction des intitulés de poste ;
- améliorer l’identification de l’entreprise ;
- normaliser davantage les noms d’entreprises ;
- améliorer la détection de la source ;
- enrichir les règles françaises et anglaises ;
- réduire les faux positifs ;
- améliorer la détection des doublons ;
- introduire éventuellement un score de confiance ;
- mieux signaler les cas incertains à l’utilisateur.

### Pipeline cible

```text
Sujet
  ↓
Corps texte
  ↓
Métadonnées
  ↓
Classification
  ↓
Extraction entreprise / poste / source
  ↓
Score de confiance éventuel
  ↓
Validation humaine si nécessaire
```

---

## 📧 Connecteurs email

### État actuel

Connecteurs disponibles :

- Gmail via API Google et OAuth ;
- Outlook / Microsoft 365 via Microsoft Graph ;
- IMAP générique.

### Améliorations prévues

- état de connexion OAuth plus précis ;
- distinction entre jeton présent, expiré ou réellement valide ;
- meilleur retour utilisateur lors d’un échec ;
- simplification de la reconnexion ;
- tests de renouvellement OAuth ;
- prise en charge de fournisseurs IMAP supplémentaires ;
- amélioration du diagnostic des erreurs IMAP ;
- désactivation / réactivation simplifiée des comptes.

---

## 📊 Statistiques et pilotage

### Objectif

Transformer le tracker en véritable outil de suivi.

### Indicateurs envisagés

- nombre total de candidatures ;
- répartition par statut ;
- répartition par source ;
- taux de réponse ;
- taux d’entretien ;
- taux de refus ;
- délai moyen avant réponse ;
- candidatures sans réponse ;
- évolution du nombre de candidatures dans le temps ;
- complétude des fiches ;
- efficacité des différentes sources.

Les indicateurs devront rester compatibles avec le modèle de statuts simplifié actuellement utilisé.

---

## 🔐 Sécurité et confidentialité

### Objectif

Préparer une utilisation plus large du projet sans dégrader la confidentialité des emails.

### Travaux envisagés

- validation plus stricte des entrées ;
- meilleure gestion des erreurs sensibles ;
- journalisation technique adaptée ;
- sauvegardes de la base ;
- stratégie de restauration ;
- politique de conservation des emails ;
- suppression complète des données utilisateur ;
- audit des permissions OAuth ;
- gestion des migrations de base ;
- documentation de la gestion des secrets ;
- préparation à un éventuel déploiement distant.

---

## 🧱 Architecture et qualité

### Prochaines améliorations

- introduire une factory Flask `create_app()` ;
- découper progressivement les routes en Blueprints ;
- réduire le couplage entre Web, base et logique métier ;
- ajouter un accès direct par identifiant pour certaines entités ;
- renforcer le typage ;
- compléter les annotations des réponses API ;
- poursuivre le nettoyage des fonctions historiques ;
- uniformiser le style des modules ;
- compléter les tests de régression.

### CI envisagée

Automatiser :

```text
Tests
  ↓
Ruff
  ↓
Format
  ↓
Pyright
  ↓
Validation du build
```

---

## 🖥️ V2 — Application Desktop

### Objectif

Simplifier l’installation et l’utilisation sur ordinateur.

### Plateformes visées

- Linux ;
- Windows.

### Fonctions envisagées

- installation simplifiée ;
- assistant de configuration ;
- démarrage automatique du serveur et du worker ;
- ajout guidé des comptes email ;
- journal de diagnostic ;
- sauvegarde et restauration ;
- mise à jour simplifiée.

---

## 📱 V2.5 — Mobile

### Objectif

Permettre la consultation et la mise à jour du suivi depuis un téléphone.

### Première version envisagée

- consultation des candidatures ;
- recherche ;
- modification du statut ;
- ajout de notes ;
- création manuelle ;
- consultation de l’historique ;
- notifications ;
- synchronisation avec le moteur principal.

Le mobile serait dans un premier temps un client de consultation et de suivi, tandis que les connecteurs email resteraient gérés par le backend principal.

---

## 👥 V3 — Multi-utilisateur / établissement

### Objectif

Faire évoluer Job Tracker vers une solution utilisable par plusieurs apprenants ou utilisateurs.

### Évolutions envisagées

- authentification ;
- comptes utilisateurs ;
- séparation stricte des données ;
- rôles ;
- gestion de promotions ou groupes ;
- tableau de bord pédagogique ;
- statistiques agrégées ;
- hébergement maîtrisé ;
- conformité RGPD ;
- politique de conservation des données ;
- gestion centralisée ou individuelle des connecteurs.

Cette phase nécessiterait une évolution importante de l’architecture actuellement locale.

---

## 🧠 Pistes futures

Selon les besoins réels :

- suggestions de relance ;
- rappels ;
- meilleure détection des candidatures sans réponse ;
- analyse sémantique optionnelle ;
- extraction assistée par IA en option ;
- API publique ;
- plugins ou intégrations supplémentaires ;
- rapprochement entre candidatures et offres conservées par l’utilisateur.

---

## 🚫 Hors périmètre actuel

Les éléments suivants ne font pas partie du périmètre actuel :

- bot Discord ;
- scraping direct de sites d’emploi ;
- agrégation automatique d’annonces sans API ou connecteur officiel ;
- automatisation de candidatures sur des plateformes tierces.

Le projet reste centré sur le suivi des candidatures de l’utilisateur à partir de ses emails, de ses saisies manuelles et de connecteurs autorisés.

---

## 🎯 Direction générale

L’objectif à court terme est de consolider le prototype actuel avant d’élargir son périmètre.

La priorité est donc :

```text
Fiabilité du moteur
        ↓
Connecteurs robustes
        ↓
Qualité / sécurité
        ↓
Statistiques
        ↓
Industrialisation
        ↓
Desktop / Mobile
        ↓
Multi-utilisateur
```

Cette progression reste volontairement adaptable afin de pouvoir présenter régulièrement l’évolution réelle du projet sans figer trop tôt les choix techniques.
