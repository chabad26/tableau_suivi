# Sécurité : contrôles et limites

Revue du code et validation locale sur cette branche, le 2 novembre 2026. Cette revue ciblée ne constitue ni un audit exhaustif ni un test des vrais fournisseurs. Les bases et jetons réels ne sont pas utilisés pour la validation.

## Isolation des utilisateurs

Les routes personnelles obtiennent `user_id` depuis la session Flask-Login. Un `user_id` fourni dans le formulaire de scan est ignoré. Le chargement de session refuse les utilisateurs désactivés. Les rôles sont enregistrés, mais ne donnent pas d'accès transversal implicite.

Les modules `owned_applications`, `owned_imap` et `owned_jobs` qualifient les ressources avec leur propriétaire. Les lectures d'emails vérifient aussi leur lien à une candidature du même utilisateur. Une ressource d'autrui est absente de la vue personnelle ; les détails de candidature renvoient 404.

Le worker sélectionne uniquement les jobs `scan` ayant un propriétaire non NULL et actif. Réservation et déduplication utilisent `BEGIN IMMEDIATE`. Les anciens jobs historiques restent présents : ils ne sont ni réservés ni modifiés par la récupération du nouveau worker. Un verrou de fichier impose un seul worker par base. Les anciens processus doivent être arrêtés avant de lancer cette version ; un verrou ne peut pas arrêter un programme déjà lancé qui l'ignorerait.

## Import et checkpoints

L'import effectue une transaction atomique et revérifie l'utilisateur actif. Son échec annule les écritures et empêche tout checkpoint. Les messages déjà importés avec succès restent conservés si une autre boîte échoue ou si la sauvegarde d'un checkpoint est refusée.

La sauvegarde du checkpoint compare dans un même UPDATE : propriétaire, activation du compte et de l'utilisateur, hôte, port, TLS, identifiant, dossier, fournisseur, méthode d'authentification et anciennes valeurs UID/UIDVALIDITY. Un checkpoint devenu incohérent est refusé. Le curseur ne peut pas reculer dans une même génération UIDVALIDITY. Cette comparaison est une garde contre les modifications concurrentes ; elle ne constitue pas un verrou distribué sur la configuration pendant tout le scan et ne détecte pas une modification suivie d'un retour strictement identique entre deux contrôles.

Un échec de lecture d'UID laisse le point de reprise avant cet UID et marque la synchronisation partielle. Sans UIDVALIDITY, aucun checkpoint fiable n'est écrit. La déduplication permet de rejouer les messages après un incident entre commit d'import et sauvegarde du curseur.

## OAuth et transport

- Le nouveau scanner passe un authentificateur privé ; il n'utilise pas les fonctions d'autorisation globales Gmail/Microsoft. Les tests font échouer le chemin global s'il est appelé.
- Les fournisseurs OAuth vérifient l'identité attendue. Aucun mot de passe Gmail/Microsoft ne remplace OAuth dans ce parcours.
- Les caches utilisent `oauth/users/<user_id>/accounts/<account_id>/` sous le répertoire de la base. Un compte réattribué ne récupère donc pas le cache de son ancien propriétaire.
- Écriture temporaire, fsync et remplacement atomique ; fichier 0600, répertoire final 0700 ; création exclusive disponible. Un verrou `fcntl` protège le cycle lecture/rafraîchissement/écriture.
- Les liens symboliques sur le fichier ou dans ses répertoires sont refusés. La protection suppose que le répertoire des données et ses parents restent sous le contrôle de l'administrateur local ; elle ne prétend pas résister à un administrateur malveillant ou à toutes les courses du système de fichiers.
- IMAP utilise TLS avec vérification de certificat, directement ou via STARTTLS obligatoire. L'échec de STARTTLS ferme la connexion avant toute authentification.
- Les secrets IMAP habituels restent dans le keyring ; ils ne sont pas stockés dans SQLite.

**Compatibilité :** les anciens fichiers OAuth restent intacts. Leur réutilisation automatique sous le nouveau chemin est volontairement exclue. Prévoir une migration administrative contrôlée ou une nouvelle autorisation ; aucune opération sur de vrais jetons n'a été effectuée ici.

## Routes et CSRF

CSRFProtect reste actif. Des tests utilisent de vrais jetons de formulaires et vérifient le refus des requêtes sans jeton ou avec jeton invalide. L'option de test désactivant le CSRF dans d'autres fixtures ne modifie pas la configuration normale ni la démonstration.

Routes réactivées : `POST /scan` et `GET /jobs`. `/reclassify`, les exports, les écrans/actions de connecteurs et les autres actions globales restent bloqués en 503 après connexion. Le contrôle du propriétaire n'est pas remplacé par la seule présence d'une session. Les tests vérifient aussi l'absence de fuite de jobs historiques.

Les cookies sont HttpOnly et SameSite=Lax ; Secure dépend de `APP_HTTPS=true`. Des en-têtes limitent l'intégration en iframe et la détection MIME, avec Cache-Control=no-store. La démonstration reste sur HTTP loopback avec un cookie distinct. `web.py` désactive le debugger et écoute uniquement sur 127.0.0.1.

## Logs et erreurs

Les exceptions brutes ne sont plus imprimées par le worker personnel ni par la lecture des UID. Le chemin historique des jobs applique aussi cette règle. Les messages enregistrés pour l'interface sont génériques ; les tests injectent une fausse valeur sensible et vérifient son absence dans les logs et dans le résultat enregistré.

Les adresses de boîtes et UID peuvent figurer dans les logs de scan : ce sont des métadonnées à protéger. Ne pas transmettre des journaux réels dans la démonstration. Aucun mot de passe ou jeton réel n'est affiché, enregistré ou manipulé par les tests.

## Défauts reproduits et corrections

| Constat | Correction | Preuve automatisée |
| --- | --- | --- |
| UID illisible mais job déclaré réussi | Nombre d'UID en erreur propagé jusqu'au job | `test_sync_integration` : échec partiel, reprise et doublons |
| Changement de port/TLS non comparé au checkpoint | Comparaison supplémentaire dans l'UPDATE atomique | Sous-tests de configuration concurrente |
| Cache OAuth retrouvé par un nouveau propriétaire du même compte | Chemin incluant utilisateur et compte | `test_oauth_store` : réattribution |
| Parent symbolique pouvant rediriger le cache | Refus des répertoires symboliques en lecture/écriture | `test_oauth_store` : parent symbolique |
| Texte d'exception pouvant exposer un secret | Logs réduits au type de l'erreur | `test_owned_jobs`, `test_sync_integration` |
| Transport IMAP en clair lorsque use_ssl=False | STARTTLS obligatoire et fermeture en cas d'échec | `test_imap_connector` : tests du transport |
| Tests définis hors classe et non collectés | Réintégration dans des TestCase | Découverte unittest et augmentation du nombre de tests |
| Test IMAP initialisant le chemin SQLite habituel | Héritage d'une fixture à base temporaire | Suite exécutée sans accéder à la base réelle |
| Boucle imbriquée du worker pouvant reprendre après Ctrl+C | Une seule boucle et un seul traitement d'arrêt | `test_worker` |
| Debugger actif au lancement habituel | debug=False | Revue du point d'entrée ; démo également sans debugger |

## Limites et opérations non effectuées

- Ni connexion aux vrais fournisseurs, ni renouvellement de vrais jetons, ni migration d'une base réelle, ni déploiement Internet.
- Le serveur Flask de développement n'est pas une infrastructure de production. HTTPS, limitation des tentatives de connexion, sauvegardes exploitées, supervision et déploiement nécessitent un travail distinct avant exposition réseau.
- Les anciens modules globaux sont conservés mais ne doivent pas être lancés pour traiter les utilisateurs Campus. Les scripts de migration restent des outils administratifs explicites, sans exécution automatique.
- Les limites des règles de classification persistent ; le statut Acceptée est manuel dans cette version.
- Une base à unicité globale des Message-ID garde une compatibilité restrictive jusqu'à sa migration explicite. Les erreurs sont préférées à une association entre utilisateurs.
- La démonstration prouve le comportement sous simulation. Elle ne prouve ni la validité des secrets existants ni la compatibilité effective de chaque compte fournisseur.
