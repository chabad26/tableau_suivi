# Évolutions après validation du projet

Demandes de référence : [`ajout.txt`](../ajout.txt). Ce suivi distingue ce qui est implémenté de ce qui reste à concevoir. Les modifications du fichier de demandes de l'utilisateur ne sont pas réécrites par l'implémentation.

## Ordre de traitement

| Lot | Demande | État |
| --- | --- | --- |
| 1 | Promotions sur les comptes : catalogue, création/affectation/retrait et affichage personnel | Implémenté ; création et affectation confirmées par l'utilisateur |
| 2 | Texte et URL de l'offre dans les candidatures ; récupération automatique étudiée ensuite | Testé et approuvé par l'utilisateur ; pas de récupération automatique |
| 3 | Améliorer la détection du poste à partir des emails et de l'offre | Implémenté, à tester par l'utilisateur ; corrections manuelles préservées |
| 4 | Dashboard chiffré : statuts, historique et accès pédagogique à l'ajout de formations/promotions | Implémenté ; chiffres personnels apprenants et agrégats apprenants pour l'équipe pédagogique (`admin`), à tester par l'utilisateur |
| 5 | CV et lettres de motivation, annotations et messages | À réaliser ; échanges apprenant et équipe pédagogique (`admin`) confirmés par l'utilisateur |
| 6 | Affichage HTML nettoyé des emails | À réaliser |
| 7 | Couleurs du campus | À réaliser ; charte ou couleurs officielles à fournir |
| 8 | Documentation de déploiement et de maintenance en production | À réaliser ; destinée à un autre apprenant |

## Lot 1 : promotions

Le catalogue est administrable, sans liste de formations figée. L'utilisateur a confirmé le format **formation + session**, par exemple **GRC 2026–2027** ou **Data 2026–2027**. Le champ libre existant permet ces libellés. Aucun libellé ni aucune affectation ne sont imposés aux comptes existants. Les libellés sont proposés dans le backoffice ; le compte personnel affiche sa promotion courante.

La table des promotions et la référence facultative sur les utilisateurs sont ajoutées par la migration habituelle d'initialisation. Les tests de migration utilisent une ancienne table sans cette référence, avec vérification de la conservation des données et d'une seconde initialisation sans effet supplémentaire.

Les affectations passent uniquement par les administrateurs actifs, avec CSRF sur les formulaires et vérification des droits dans les transactions des services. Elles n'accordent aucun nouveau droit sur les données. Les mots de passe et jetons ne figurent pas dans les listes de comptes ou de promotions. La base personnelle, les caches OAuth et les emails réels ne sont pas utilisés par les tests.

Utilisation : consulter [la procédure d'administration](ADMINISTRATION.md#creer-et-affecter-des-promotions).

Validation du 12 novembre 2026 : suite Python complète de **266 tests réussis**, puis relance des **10 tests du lot promotions** après renforcement du contrôle des identifiants SQLite. Les **7 tests JavaScript** du suivi de connexion passent également. Ruff, formatage, Pyright et `git diff --check` sont conformes. Aucun déploiement ni changement de compte personnel n'a été effectué par ces contrôles.

## Lot 2 : texte et URL de l'offre

Les champs facultatifs sont disponibles à la création et sur chaque fiche de candidature. L'offre possède son propre formulaire pour éviter qu'une simple sauvegarde du texte fige le statut ou le poste en correction manuelle. L'affichage préserve les retours à la ligne et échappe le HTML. Le lien HTTP(S) ne provoque aucun téléchargement automatique.

La migration est additive et idempotente. Les anciens comptes, candidatures et offres ne sont pas réaffectés. Import et réanalyse préservent les offres enregistrées. Les tests utilisent une base temporaire et vérifient notamment la propriété, le CSRF, les URL actives interdites, l'absence de perte de saisie et la conservation des autres champs de candidature.

Utilisation et limites : [conserver une offre d'emploi](OFFRES.md). L'exploitation du texte pour la détection de poste est implémentée au lot 3 ; la récupération depuis une URL reste à étudier.

Validation du lot 2 : **278 tests Python réussis** sur la suite complète, dont **12 tests dédiés aux offres**, puis relance des tests d'offres après renforcement du rejet des caractères de contrôle dans les URL. Ruff, formatage, Pyright et `git diff --check` sont conformes. Les contrôles utilisent uniquement des bases temporaires ; aucune annonce ni aucun email réel n'a été téléchargé.

## Lot 3 : détection du poste

Le texte de l'offre et les emails liés alimentent une détection locale. L'offre fournit en priorité un libellé explicite ou un titre de début d'annonce ; les recommandations et les libellés contradictoires sont écartés. La réanalyse enrichit les fiches automatiques, tandis que les fiches corrigées manuellement conservent leurs détails. Une suggestion visible et son bouton **Utiliser ce poste** permettent à l'utilisateur de choisir explicitement un titre avant de sauvegarder le formulaire.

La saisie manuelle n'est plus refusée parce que son score heuristique est égal ou inférieur à celui du titre existant. Les règles d'emails sont étendues aux intitulés d'offres cités dans le sujet ou un accusé de candidature. Les domaines Data, GRC et d'autres métiers sont pris en compte sans figer le catalogue des formations.

Procédure et limites : [détection du poste](DETECTION_POSTES.md). Les tests utilisent des données fictives ; aucune réanalyse de la base personnelle n'est effectuée pendant le développement.

Validation du lot 3 : **290 tests Python réussis**, dont 11 tests dédiés aux suggestions et à leur intégration, et **8 tests JavaScript** pour le suivi de connexion et le remplissage explicite du poste. Ruff, formatage, Pyright et `git diff --check` sont conformes. La correction manuelle d'un titre de score égal ou inférieur est couverte par les tests ; la validation utilisateur de ce lot reste à effectuer.

## Décision confirmée pour le dashboard

Le campus peut créer de nouveaux types de formation : aucune liste Data/GRC n'est codée en dur. Le dashboard propose l'accès **Ajouter une formation / promotion**, visible uniquement à l'équipe pédagogique autorisée, vers le catalogue existant. Les filtres lisent ce catalogue et conservent les contrôles d'accès sur les chiffres. Les candidatures détaillées ne sont pas affichées sur le dashboard.

L'utilisateur a confirmé deux profils : **apprenant** pour ses seuls chiffres, et **équipe pédagogique (`admin`)** pour les chiffres agrégés des apprenants par promotion. Il n'y a pas de profil formateur à proposer pour les nouveaux comptes. Les anciens enregistrements de rôle `trainer` sont conservés par compatibilité, sans accès au nouveau dashboard ni réattribution automatique.

Le lot 4 fournit les cartes de statuts actuels, les évolutions mensuelles sur 6 ou 12 mois et un journal de changements qui démarre à l'installation. Les états de départ ne sont pas présentés comme des changements historiques. Les chiffres des premières détections utilisent les dates déjà enregistrées, séparément des dates d'observation des statuts. Voir [le périmètre et les limites du dashboard](DASHBOARD.md).

Ajout demandé ensuite par l'utilisateur : tableau des **statistiques par apprenant**, réservé à l'équipe pédagogique en vue campus, avec identifiant email, promotion, état du compte, total et compteurs par statut. Il suit le filtre de promotion et inclut les apprenants sans candidature. Les vues personnelles ne sélectionnent aucune de ces lignes ; les détails des candidatures restent exclus. Cette demande autorise les identifiants des apprenants dans ce tableau pédagogique, en complément des seuls agrégats initiaux.

Validation du lot 4 : **305 tests Python réussis**, dont 15 tests dédiés au dashboard et au journal, et **9 tests JavaScript**. Les 37 tests dashboard/promotions/offres ont également été relancés avec les avertissements de ressource traités comme des erreurs, après fermeture explicite des connexions des fixtures de migration. Ruff, formatage, Pyright et `git diff --check` sont conformes. Aucun journal réel, scan ou changement de compte personnel n'a été exécuté pendant les tests ; l'historique réel commencera au déploiement de cette version.

## Décision confirmée pour les CV et lettres de motivation

L'apprenant et l'équipe pédagogique (`admin`) doivent pouvoir consulter les documents et échanger des annotations et des messages. Cette précision remplace la première formulation « formateur ». Avant ce lot, définir les règles d'accès aux documents des apprenants, la conservation des versions et les échanges. Le droit de consulter les agrégats du dashboard ne donne pas encore accès aux documents ou aux candidatures détaillées d'un autre utilisateur.
