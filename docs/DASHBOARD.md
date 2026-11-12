# Tableau de bord chiffré

## Accéder aux indicateurs

Après redémarrage de Flask et du worker, ouvrir **Tableau de bord** dans la navigation (`/dashboard`). Les écrans détaillés des candidatures restent séparés.

Deux profils sont retenus, conformément à la décision du campus :

- **Apprenant (`student`)** : uniquement ses chiffres personnels. Le filtre de promotion ne permet jamais de consulter ses camarades.
- **Équipe pédagogique (`admin`)** : vue campus agrégée des apprenants, toutes promotions ou une promotion choisie. **Mes chiffres** permet de retrouver le suivi personnel d'un membre de l'équipe ; ses candidatures personnelles ne sont pas incluses dans les chiffres des apprenants.

Le dashboard ne sélectionne ni entreprise, ni poste, ni note, ni texte d'offre, ni corps d'email. Il ne donne pas accès aux fiches détaillées d'autrui. Les autorisations sont vérifiées à partir du rôle et de l'activation en base, dans la transaction de lecture, et pas seulement par les liens affichés.

À la demande du campus, la vue pédagogique comporte aussi le tableau **Statistiques par apprenant**. Chaque ligne affiche l'adresse de connexion de l'apprenant pour l'identifier, sa promotion, l'état actif/désactivé du compte, le total de candidatures et les compteurs par statut affiché. Les apprenants sans candidature sont inclus avec des zéros. Ce tableau est sélectionné et affiché uniquement en vue campus pour l'équipe pédagogique, jamais en vue personnelle. Il ne contient ni lien vers une candidature étrangère, ni contenu de candidature ou d'email.

L'ancien rôle `trainer` reste lisible dans la base pour compatibilité, mais n'est pas un profil du dashboard. Il n'est plus proposé à la création dans le backoffice ou le script terminal. Aucun ancien compte n'est automatiquement supprimé ou réattribué.

## Chiffres et filtres

Les cartes donnent les statuts **actuellement affichés**, en tenant compte des corrections manuelles : total, envoyées, reçues, entretiens, refus, acceptées, sans réponse et à analyser. Elles portent sur toutes les dates. Un compteur indique le nombre d'apprenants dans le périmètre campus, ou le compte personnel en vue individuelle.

Le tableau par apprenant utilise exactement le même filtre de promotion et le même périmètre que les cartes ; la somme des lignes correspond aux totaux affichés. Ses chiffres portent également sur toutes les dates. Le choix de 6 ou 12 mois concerne uniquement l'évolution mensuelle.

Le tableau mensuel couvre les **6 ou 12 derniers mois calendaires**, mois en cours inclus, en UTC. Il indique :

- **Premières détections** : nombre de candidatures dont la date `first_seen` se situe dans le mois. Cette date peut provenir d'un email ancien importé plus tard ; ce n'est donc pas la date du scan ni nécessairement la date d'envoi de la candidature.
- **Changements enregistrés** : nombre de changements du statut affiché observés après mise en place du journal.
- **Vers chaque statut** : répartition de ces changements selon le statut d'arrivée. Une même candidature peut compter plusieurs changements.

Les périodes sans données affichent zéro. Les dates invalides ou futures ne sont pas intégrées à l'évolution de la période ; les candidatures restent comptées dans les statuts actuels. Les comptes apprenants désactivés et leurs candidatures conservées restent inclus dans les chiffres campus ; la désactivation ne supprime pas les données. Les anciennes candidatures sans propriétaire, ou sans compte propriétaire correspondant, restent exclues.

Le catalogue des promotions est lu en base : une nouvelle formation/session est disponible sans modification du code. Le filtre **Sans promotion renseignée** reste utilisable en vue campus. Les filtres s'appliquent aux cartes et à l'évolution. Les données sont rattachées à la **promotion actuelle** du compte : ce lot ne reconstitue pas les promotions antérieures d'une personne.

Pour l'équipe pédagogique, **Ajouter une formation / promotion** ouvre la section du catalogue dans l'administration. La création et l'affectation conservent les contrôles de rôle et de CSRF existants.

La fin d'une synchronisation de connexion réussie actualise aussi cette page. En dehors de ce suivi, utiliser **Actualiser les chiffres** ou recharger la page. Les calculs sont locaux, sans téléchargement d'email ni dépendance à Internet ; le worker reste nécessaire aux scans et réanalyses habituels.

## Historique : ce qui est réellement connu

L'initialisation ajoute `application_status_history` et `application_history_metadata` après la migration de propriété. Le journal ne stocke que l'identifiant de candidature, le propriétaire, le type d'observation, les codes de statut et la date UTC d'enregistrement.

Les candidatures déjà présentes reçoivent un **état de départ observé maintenant** (`snapshot`), sans inventer les changements passés ni les dater avec `first_seen`. Cet état de départ n'est pas compté comme une transition. Une nouvelle candidature reçoit une observation de création (`created`), également distincte des changements (`change`). L'initialisation suivante ne duplique pas ces observations.

Des triggers SQLite enregistrent ensuite les changements du statut effectivement affiché. Les modifications de notes, de poste et d'offre, ou les mises à jour du statut automatique masquées par un statut manuel, ne créent pas de fausse transition. Un échec transactionnel annule également les événements du lot. La réanalyse d'une ancienne candidature déjà « Sans réponse » ne crée plus de faux allers-retours vers un statut d'attente avant de l'expirer à nouveau.

La suppression d'une candidature supprime ses événements : les chiffres historiques portent sur les candidatures conservées. Un changement de propriétaire réinitialise l'historique de cette candidature avec un état de départ pour le nouveau propriétaire ; l'ancien historique n'est pas transmis. Ce journal sert aux indicateurs métier, pas à un audit de sécurité inviolable.

Sauvegarder la base avant la mise à jour de schéma et redémarrer **Flask et le worker** ensemble. Les tests n'installent ce journal que sur des bases temporaires ; ils ne collectent aucun historique réel pendant le développement.

## Validation

```bash
.venv/bin/python -m unittest tests.test_dashboard -v
node --test tests/login-sync.test.cjs tests/application.test.cjs
```

Les tests couvrent droits et révocation, absence de données détaillées dans le rendu, filtres dynamiques, exclusion du suivi personnel de l'équipe en vue campus, UTC, états de départ, absence de doublons, rollback, transfert de propriété, suppression et réanalyse répétée sans faux changements.
