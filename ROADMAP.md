🧭 Roadmap — Job Tracker

Vision

Job Tracker a pour objectif d'évoluer d'un outil personnel de suivi des candidatures vers une plateforme générique, sécurisée et multi-source, capable de centraliser automatiquement les candidatures issues des emails et des saisies utilisateur.

L'objectif à terme est de proposer une solution utilisable sur Linux, Windows et Android, avec des connecteurs modernes vers Gmail, Outlook / Microsoft 365 et d'autres services.

✅ MVP actuel

Envoyée
Reçue
Entretien
Refus
Sans réponse
À analyser

distinguer plusieurs états :

Envoyée
   ↓
Reçue
   ↓
Entretien
   ↓
Refus / Sans réponse

À analyser ;

corriger manuellement les informations détectées ;

créer et supprimer une candidature ;

fusionner des candidatures ;

consulter l'historique des emails associés ;

afficher le contenu complet d'un email dans une section dépliable ;

rechercher et filtrer les candidatures ;

réanalyser les emails déjà détectés ;

exporter les données en CSV et Excel ;

conserver les données dans une base SQLite locale.

🔧 V0.9 — Fiabilisation du moteur d'extraction

Objectif

Améliorer la qualité des informations détectées automatiquement.

Évolutions prévues

extraction plus fine des intitulés de poste ;

analyse plus robuste du sujet et du corps des emails ;

meilleure gestion des formulations inclusives ;

prise en charge plus large des emails en français et en anglais ;

meilleure identification de l'entreprise ;

normalisation des entreprises et des sources ;

amélioration de la détection des doublons ;

score de confiance sur les informations extraites ;

validation humaine lorsqu'une extraction est incertaine.

Pipeline cible

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

## ✅ Connecteurs email

Connecteurs actuellement disponibles :

- Gmail via API Google et OAuth ;
- Outlook / Microsoft 365 via Microsoft Graph ;
- IMAP générique pour les fournisseurs compatibles.

L’architecture des connecteurs est mutualisée afin de permettre l’ajout de nouvelles sources sans modifier le moteur principal.

🔐 V1.1 — Sécurité et confidentialité

Objectif

Préparer l'utilisation du projet dans un environnement réel.

Évolutions prévues

secrets déplacés dans des variables d'environnement ;

stockage sécurisé des jetons OAuth ;

gestion des permissions ;

journalisation des actions importantes ;

politique de conservation des emails ;

export des données utilisateur ;

suppression des données utilisateur ;

sauvegardes ;

migrations de base de données ;

validation et nettoyage des entrées ;

audit des connecteurs externes.

📊 V1.2 — Statistiques et accompagnement

Objectif

Transformer le tracker en outil de pilotage.

Indicateurs envisagés

nombre total de candidatures ;

répartition par statut ;

répartition par source ;

taux de réponse ;

taux d'entretien ;

taux de refus ;

taux d'offre ;

délai moyen de réponse ;

candidatures sans réponse ;

évolution dans le temps ;

complétude des candidatures ;

efficacité des différentes sources.

Funnel envisagé

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

Les refus peuvent intervenir à plusieurs étapes du parcours.

🖥️ V2.0 — Application Desktop

Objectif

Simplifier le déploiement et l'utilisation sur ordinateur.

Plateformes

Linux ;

Windows.

Fonctions prévues

installation simplifiée ;

assistant de configuration ;

ajout guidé des comptes email ;

lancement automatique en arrière-plan ;

interface locale ;

mises à jour ;

sauvegardes ;

journal de diagnostic.

📱 V2.5 — Android

Objectif

Permettre le suivi des candidatures depuis un téléphone.

Première version envisagée

consultation des candidatures ;

modification du statut ;

ajout de notes ;

création manuelle ;

consultation de l'historique ;

notifications ;

synchronisation avec le moteur principal.

Dans un premier temps, Android serait principalement un client de consultation et de suivi, les connecteurs Gmail et Microsoft restant gérés par le backend ou le moteur principal.

👥 V3.0 — Version établissement / multi-utilisateur

Objectif

Faire évoluer Job Tracker vers une solution utilisable par plusieurs apprenants.

Évolutions prévues

authentification ;

comptes utilisateurs ;

séparation stricte des données ;

rôles :

apprenant ;

pédagogue ;

administrateur ;

gestion des promotions ;

tableau de bord pédagogique ;

statistiques anonymisées ou agrégées ;

hébergement maîtrisé ;

gestion centralisée des connecteurs ;

conformité RGPD ;

politique de conservation des données.

🧠 Évolutions futures

Selon les besoins et les retours utilisateurs :

analyse sémantique plus avancée ;

détection automatique de nouvelles plateformes de recrutement ;

suggestions de relance ;

rappels ;

détection des candidatures sans réponse ;

rapprochement entre offres et candidatures ;

extraction assistée par IA en option ;

API publique ;

plugins ou intégrations supplémentaires.

🚫 Hors périmètre actuel

Les éléments suivants ne font plus partie de la roadmap :

bot Discord ;

récupération automatique ou scraping d'annonces publiées sur des sites d'emploi ;

agrégation directe d'offres depuis des plateformes externes sans connecteur officiel.

Le projet reste centré sur le suivi des candidatures de l'utilisateur, à partir de ses emails, de ses saisies manuelles et de connecteurs autorisés.

🎯 Objectif final

Passer d'un tracker personnel capable d'analyser Thunderbird à une plateforme indépendante du client mail, connectée à Gmail et Microsoft, disponible sous Linux, Windows et Android, avec une architecture sécurisée, générique et adaptée à un usage multi-utilisateur.
