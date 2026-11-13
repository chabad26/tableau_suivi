# Sécurité : contrôles et limites

Revue du code et validation locale sur cette branche, le 2 novembre 2026. Cette revue ciblée ne constitue ni un audit exhaustif ni un test des vrais fournisseurs. Les bases et jetons réels ne sont pas utilisés dans les tests automatisés. Un contrôle réel séparé, explicitement autorisé, est décrit dans `INTEGRATION.md`.

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

**Compatibilité :** les anciens fichiers OAuth restent intacts. Leur réutilisation automatique sous le nouveau chemin est volontairement exclue. Prévoir une migration administrative contrôlée ou une nouvelle autorisation ; le contrôle autorisé de copie des caches réels est décrit dans `INTEGRATION.md`.

## Routes et CSRF

CSRFProtect reste actif. Des tests utilisent de vrais jetons de formulaires et vérifient le refus des requêtes sans jeton ou avec jeton invalide. L'option de test désactivant le CSRF dans d'autres fixtures ne modifie pas la configuration normale ni la démonstration.

Routes personnelles réactivées : `POST /scan`, `POST /reclassify`, `GET /jobs`, liste/création/édition/activation et tests de connexion des connecteurs. Le backoffice `/admin/users` est réservé aux administrateurs actifs. Les exports et les anciennes actions globales non migrées restent bloqués en 503 après connexion. L'autorisation OAuth interactive n'est pas ajoutée au Web. Le contrôle du propriétaire n'est pas remplacé par la seule présence d'une session. Les tests vérifient aussi l'absence de fuite de jobs historiques.

Les cookies sont HttpOnly et SameSite=Lax ; Secure dépend de `APP_HTTPS=true`. Des en-têtes limitent l'intégration en iframe et la détection MIME, avec Cache-Control=no-store. La démonstration reste sur HTTP loopback avec un cookie distinct. `web.py` désactive le debugger et écoute uniquement sur 127.0.0.1.

## Logs et erreurs

Les exceptions brutes ne sont plus imprimées par le worker personnel ni par la lecture des UID. Le chemin historique des jobs applique aussi cette règle. Les messages enregistrés pour l'interface sont génériques ; les tests injectent une fausse valeur sensible et vérifient son absence dans les logs et dans le résultat enregistré.

Le résumé du scan, les erreurs filtrées par compte et le résumé d'import sont affichés pour distinguer les phases. Les messages de configuration fixes sont identifiés par une exception dédiée ; les exceptions imprévues du gestionnaire de secrets n'exposent que leur type.

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

- Aucun accès fournisseur ni vrai jeton dans les tests automatisés. Le contrôle réel autorisé de la branche intégrée est décrit séparément dans `INTEGRATION.md`. Aucun déploiement Internet ni migration du schéma de la base réelle n’a été réalisé.
- Le serveur Flask de développement n'est pas une infrastructure de production. HTTPS, limitation des tentatives de connexion, sauvegardes exploitées, supervision et déploiement nécessitent un travail distinct avant exposition réseau.
- Les anciens modules globaux sont conservés mais ne doivent pas être lancés pour traiter les utilisateurs Campus. Les scripts de migration restent des outils administratifs explicites, sans exécution automatique.
- Les limites des règles de classification persistent ; le statut Acceptée est manuel dans cette version.
- Une base à unicité globale des Message-ID garde une compatibilité restrictive jusqu'à sa migration explicite. Les erreurs sont préférées à une association entre utilisateurs.
- La démonstration prouve le comportement sous simulation. Elle ne prouve ni la validité des secrets existants ni la compatibilité effective de chaque compte fournisseur.

## Dashboard pédagogique

Le dashboard vérifie le rôle et l’activation dans la transaction de lecture. L’apprenant est limité à son identifiant, même avec un filtre de promotion forgé. La vue campus est réservée au rôle `admin` de l’équipe pédagogique et agrège uniquement les apprenants, sans sélection d’entreprise, poste, note, offre ou contenu mail. Les candidatures détaillées et messageries d’autrui restent inaccessibles. L’ancien rôle `trainer` n’est pas proposé à la création et ne reçoit pas d’accès au dashboard ; les anciens comptes sont conservés sans promotion automatique.

Le journal ne contient que les identifiants nécessaires au périmètre, des codes de statut et leurs dates d’observation. Les états initiaux ne sont pas des preuves d’une transition passée. Le transfert de propriété réinitialise l’historique pour éviter de transmettre celui de l’ancien propriétaire ; les écritures sont annulées avec la transaction métier en cas d’échec. Ce journal applicatif n’est pas présenté comme un audit de sécurité inviolable. Voir [les règles du dashboard](DASHBOARD.md).


## Documents privés et échanges

Le lot CV/LM accorde explicitement à l’équipe pédagogique active le droit de consulter et commenter les documents des apprenants. Un apprenant n’a accès qu’à ses propres fichiers et échanges. Les propriétaires et auteurs viennent des contrôles serveur ; des champs de formulaire forgés ne permettent pas de les remplacer. L’équipe ne peut pas déposer une version à la place d’un apprenant ni supprimer ses fichiers. Tous les POST sont protégés par CSRF.

Le stockage est hors du répertoire statique, avec noms physiques générés, permissions privées et refus des symlinks. Les téléchargements sont autorisés avant lecture des fichiers, vérifiés par taille et empreinte, servis en pièce jointe sans cache et sans HTML exécutable dans la page. Les contrôles de signature et de structure ne sont pas présentés comme un antivirus. Le dépôt de fichiers reste limité à 10 Mo et ne relève pas la limite des autres formulaires.

Les sauvegardes doivent couvrir de manière cohérente la base et les fichiers. Une suppression efface également les versions et leurs échanges ; la mise à l’écart temporaire des fichiers permet de les remettre en place si la transaction échoue. Le comportement en cas d’interruption de processus et les modalités de restauration sont décrits dans [DOCUMENTS.md](DOCUMENTS.md).

### Corps HTML des emails

Le HTML source conservé en base est non fiable. La fiche applique le nettoyeur nh3 à liste restrictive puis isole le résultat dans une iframe `srcdoc` échappée, avec sandbox et CSP interdisant scripts, formulaires et ressources distantes. Toutes les images et les styles d'expéditeur sont retirés. Seuls les liens HTTP/HTTPS absolus restent cliquables, sans accès à la fenêtre d'origine et sans référent. Les droits restent limités au propriétaire de la candidature. Voir [le rendu HTML et ses limites](EMAILS_HTML.md).
