# Évolutions après validation du projet

Demandes de référence : [`ajout.txt`](../ajout.txt). Ce suivi distingue ce qui est implémenté de ce qui reste à concevoir. Les modifications du fichier de demandes de l'utilisateur ne sont pas réécrites par l'implémentation.

## Ordre de traitement

| Lot | Demande | État |
| --- | --- | --- |
| 1 | Promotions sur les comptes : catalogue, création/affectation/retrait et affichage personnel | Implémenté ; création et affectation confirmées par l'utilisateur |
| 2 | Texte et URL de l'offre dans les candidatures, conservés manuellement | Testé et approuvé par l'utilisateur ; pas de récupération automatique |
| 3 | Améliorer la détection du poste à partir des emails et de l'offre | Implémenté, à tester par l'utilisateur ; corrections manuelles préservées |
| 4 | Dashboard chiffré : statuts, historique et accès pédagogique à l'ajout de formations/promotions | Implémenté ; chiffres personnels apprenants et agrégats apprenants pour l'équipe pédagogique (`admin`), à tester par l'utilisateur |
| 5 | CV et lettres de motivation, annotations et messages | Implémenté ; PDF/DOCX, versions, échanges apprenant/équipe pédagogique, à tester par l'utilisateur |
| 6 | Affichage HTML nettoyé des emails | Implémenté ; nettoyage, iframe isolée et texte de secours ; validé par l’utilisateur |
| 7 | Couleurs du campus | Implémenté et validé par l’utilisateur ; logo Campus et footer Olidev intégrés |
| 8 | Documentation de déploiement et de maintenance en production | Guide et modèles préparés et vérifiés localement ; recette sur le futur hébergeur à effectuer |

## Lot 1 : promotions

Le catalogue est administrable, sans liste de formations figée. L'utilisateur a confirmé le format **formation + session**, par exemple **GRC 2026–2027** ou **Data 2026–2027**. Le champ libre existant permet ces libellés. Aucun libellé ni aucune affectation ne sont imposés aux comptes existants. Les libellés sont proposés dans le backoffice ; le compte personnel affiche sa promotion courante.

La table des promotions et la référence facultative sur les utilisateurs sont ajoutées par la migration habituelle d'initialisation. Les tests de migration utilisent une ancienne table sans cette référence, avec vérification de la conservation des données et d'une seconde initialisation sans effet supplémentaire.

Les affectations passent uniquement par les administrateurs actifs, avec CSRF sur les formulaires et vérification des droits dans les transactions des services. Elles n'accordent aucun nouveau droit sur les données. Les mots de passe et jetons ne figurent pas dans les listes de comptes ou de promotions. La base personnelle, les caches OAuth et les emails réels ne sont pas utilisés par les tests.

Utilisation : consulter [la procédure d'administration](ADMINISTRATION.md#creer-et-affecter-des-promotions).

Validation du 12 novembre 2026 : suite Python complète de **266 tests réussis**, puis relance des **10 tests du lot promotions** après renforcement du contrôle des identifiants SQLite. Les **7 tests JavaScript** du suivi de connexion passent également. Ruff, formatage, Pyright et `git diff --check` sont conformes. Aucun déploiement ni changement de compte personnel n'a été effectué par ces contrôles.

## Lot 2 : texte et URL de l'offre

Les champs facultatifs sont disponibles à la création et sur chaque fiche de candidature. L'offre possède son propre formulaire pour éviter qu'une simple sauvegarde du texte fige le statut ou le poste en correction manuelle. L'affichage préserve les retours à la ligne et échappe le HTML. Le lien HTTP(S) ne provoque aucun téléchargement automatique.

La migration est additive et idempotente. Les anciens comptes, candidatures et offres ne sont pas réaffectés. Import et réanalyse préservent les offres enregistrées. Les tests utilisent une base temporaire et vérifient notamment la propriété, le CSRF, les URL actives interdites, l'absence de perte de saisie et la conservation des autres champs de candidature.

Utilisation et limites : [conserver une offre d'emploi](OFFRES.md). L'exploitation du texte pour la détection de poste est implémentée au lot 3 ; la récupération automatique depuis une URL est abandonnée.

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

L'apprenant et l'équipe pédagogique (`admin`) peuvent consulter les documents et échanger des annotations et des messages. Cette précision remplace la première formulation « formateur ». L'utilisateur a confirmé les formats PDF et DOCX, la limite de 10 Mo et les annotations textuelles avec page facultative. Le lot 5 accorde explicitement l'accès aux documents des apprenants à l'équipe pédagogique, indépendamment du droit antérieur sur les seuls agrégats du dashboard. Il n'accorde pas de lecture des candidatures détaillées ou des emails d'autrui.

L'onglet **CV et lettres** permet plusieurs documents par apprenant et des versions distinctes par document. Les échanges restent rattachés à chaque version. Seul l'apprenant dépose, révise ou supprime ses fichiers ; l'équipe les consulte et commente. Les fichiers sont privés, hors des ressources statiques, et téléchargés après contrôle de rôle, propriétaire, intégrité et taille. Voir [la procédure des documents](DOCUMENTS.md), notamment la sauvegarde conjointe de la base et des fichiers.

Ajustement de parcours demandé ensuite : côté pédagogique, choisir d'abord la promotion, puis un apprenant de cette promotion. Le changement de promotion réinitialise la sélection ; les comptes sans promotion et les promotions vides sont gérés. Les anciens liens vers un apprenant retrouvent sa promotion. Les 23 tests ciblés des documents passent après cet ajustement ; les droits d'accès restent inchangés.

Validation du lot 5 : **340 tests Python réussis** sur la suite complète et **9 tests JavaScript**. Les **21 tests dédiés aux documents** ont été relancés après renforcement des contrôles DOCX, avec les avertissements de ressource traités comme des erreurs et fermeture explicite du flux multipart temporaire généré par la fixture. Ruff, formatage, Pyright et `git diff --check` sont conformes. Les fichiers sont synthétiques, les bases et le stockage temporaires ; aucun CV ou document personnel n'est déposé, lu ou supprimé par ces tests.


## Correction de synchronisation : changement de boîte et de nom affiché

Le regroupement des nouveaux emails exploite désormais les références du fil, puis une combinaison stricte expéditeur/sujet/réponse/proximité temporelle. Il reste limité au propriétaire et refuse les rapprochements de postes explicitement différents ou les candidats ambigus. Une réponse reçue dans une autre boîte n'est donc plus obligatoirement traitée comme une nouvelle candidature si le nom affiché de son expéditeur change. Les anciens doublons restent intacts, notamment lorsque leurs corrections manuelles divergent ; aucun choix de statut n'est imposé.

Validation : 319 tests Python réussis sur la suite complète, dont 10 tests dédiés au rapprochement. Le pipeline fictif vérifie la conservation des références après scan/import ; la migration d'unicité des emails est également testée avec ces métadonnées. Aucun scan réel, renouvellement OAuth ou fusion de candidature personnelle n'est exécuté pendant ces contrôles.

## Lot 6 : affichage des emails HTML

Les prochains scans archivent le corps HTML séparément du texte d'analyse. Les fiches présentent sa mise en forme après nettoyage par nh3 et isolation dans une iframe avec sandbox et CSP. Les images et contenus actifs sont désactivés, les liens HTTP/HTTPS s'ouvrent après clic dans un nouvel onglet. Le texte archivé reste consultable ; les anciennes archives uniquement textuelles restent en texte. Les droits de consultation des emails ne changent pas. Voir [l'affichage des emails HTML](EMAILS_HTML.md).

Validation du lot 6 : **351 tests Python réussis** sur la suite complète avec les avertissements de ressource traités comme des erreurs, et **9 tests JavaScript** réussis. Les 31 tests ciblés HTML/migration/synchronisation passent également. Ruff, formatage, Pyright et `git diff --check` sont conformes. Une connexion non fermée dans une ancienne fixture SQLite a été corrigée. Les données et transports sont fictifs ; aucun scan personnel ni récupération rétroactive de HTML n'a été exécuté. La vérification visuelle reste à effectuer par l'utilisateur.

## Lot 7 : couleurs du Campus

L'interface conserve ses fonds sombres et adopte les accents rose, bleu et orange du site du Campus, avec des variantes de rose adaptées au contraste des liens et boutons. Un bandeau commun identifie le Campus et Job Tracker. Le focus clavier est renforcé et les couleurs des statuts restent distinctes. Les ressources du thème sont locales. Voir [les références et vérifications visuelles](IDENTITE_VISUELLE.md).

Validation : 34 tests existants web/dashboard/synchronisation de connexion réussis, Ruff, formatage et `git diff --check` conformes ; contrastes des nouveaux textes vérifiés et captures Firefox examinées sur ordinateur et mobile, à partir de données temporaires. Aucun traitement de données personnelles n'est déclenché.


## Lot 8 : déploiement et exploitation

Le [guide de déploiement en production](DEPLOIEMENT_PRODUCTION.md) décrit l'installation Linux/Python 3.14, un compte de service dédié, Gunicorn derrière Nginx HTTPS et un worker unique. Le dossier `deploy/` fournit le fichier d'environnement et les unités systemd Web/worker ainsi que le site Nginx ; `requirements-prod.txt` fixe Gunicorn 27.0.1 et inclut les dépendances applicatives. Le guide explique le premier administrateur, les migrations, la recette, les mises à jour et le retour arrière, ainsi que la sauvegarde cohérente de SQLite, documents, OAuth, configuration et trousseau externe.

Les limites du produit sont explicites : consentement OAuth Web absent, parcours Microsoft administratif séparé, trousseau headless à provisionner pour les mots de passe IMAP, protection des tentatives de connexion à préparer avant exposition large. Aucun secret réel n'est copié ni service système installé sur le poste de développement. La correction utilisateur retirant le texte Olidev en doublon est conservée ; le logo assure désormais le nom accessible du lien.

Validation locale : Gunicorn `--check-config` réussi puis HTTP 200 sur `/login` avec une base temporaire ; worker réel exécutant une réanalyse fictive sans boîte configurée ; deux unités vérifiées par `systemd-analyze verify` avec chemins locaux adaptés ; configuration Nginx 1.28.3 vérifiée par `nginx -t` avec certificat temporaire et ports locaux non privilégiés. Les paquets de validation sont extraits/installés uniquement sous `/tmp`. Les 11 blocs shell du guide passent `bash -n` et ses liens locaux existent. Les 15 tests Web/migration d'unicité passent, ainsi que Ruff, le formatage et `git diff --check`. Aucun certificat public, DNS, backend de secrets, scan personnel ou déploiement distant n'est validé par ces contrôles.


## Périmètre confirmé : retrait de « Envoyée »

L'utilisateur a confirmé le retrait du statut « Envoyée », ainsi que l'abandon de la récupération automatique d'offres et de l'envoi de candidatures depuis le site. Aucun module actif d'envoi automatique n'a été trouvé. Le texte et le lien d'une offre restent conservables manuellement pour le suivi et l'extraction du poste.

Le statut par défaut est désormais « Reçue » ; les confirmations de dépôt, y compris les sujets indiquant qu'une candidature a été envoyée par une plateforme externe, sont classées « Reçue ». Les formulaires refusent l'ancien code, les badges et compteurs correspondants sont supprimés et la démonstration Alice/Bob utilise le nouveau statut. Le passage « Sans réponse » reste actif sur les dossiers en attente et épargne les refus.

Au prochain démarrage Web/worker, l'initialisation convertit `applications.current_status`, `applications.manual_status` et `emails.detected_status` de `SENT` vers `RECEIVED`. La conversion et le renouvellement des déclencheurs sont transactionnels : une erreur annule l'ensemble. Les propriétaires, notes, marqueurs manuels, dates et contenus d'emails sont préservés. Les événements historiques bruts restent intacts et sont regroupés dans la catégorie « Reçue » pour les graphiques, sans fabriquer de transition lors de la conversion. Les anciens schémas dépourvus de `user_id` restent pris en charge.

Les tests de conversion utilisent exclusivement des bases temporaires, avec deux propriétaires, des déclencheurs historiques simulés et un échec d'écriture provoqué. Aucune base personnelle ni aucun jeton n'est modifié pendant le développement. Faire une sauvegarde avant le redémarrage de la version sur une base existante.

Validation de ce retrait : **356 tests Python réussis**, avec avertissements de ressource traités comme des erreurs, dont 5 tests dédiés au retrait du statut ; **9 tests JavaScript** réussis. Les 33 tests ciblés conversion/stockage/dashboard passent également. Ruff, formatage, Pyright et `git diff --check` sont conformes. La démonstration et la synchronisation sont vérifiées hors ligne ; la conversion de la base réelle reste à effectuer lors du redémarrage après sauvegarde.
