# Préparer Google et Microsoft pour synchroniser les boîtes

Guide destiné à l'équipe technique du Campus, vérifié contre le code et les documentations officielles le **17 novembre 2026**. Les intitulés des consoles peuvent évoluer ; les types de client, permissions et variables ci-dessous sont les points à conserver.

## Deux étapes distinctes

1. **Le Campus enregistre son application OAuth** chez le fournisseur. Cette opération fournit la configuration qui identifie Job Tracker.
2. **Chaque titulaire autorise sa propre boîte**. Cette autorisation fournit un cache personnel renouvelable, stocké hors des fichiers publics.

Créer l'application fournisseur ou renseigner un identifiant ne suffit donc pas à synchroniser une boîte. Les connecteurs Web n'effectuent pas encore le consentement OAuth. Le compte Job Tracker et le compte Google/Microsoft sont deux identités distinctes ; l'autorisation doit correspondre à l'adresse exacte du connecteur.

| Fournisseur | Élément fourni par le fournisseur | Configuration de Job Tracker | Autorisation personnelle actuelle |
| --- | --- | --- | --- |
| Google | Fichier JSON d'un client OAuth **Application de bureau** | `GMAIL_CREDENTIALS_FILE` | Commande `authorize_gmail.py`, ou migration contrôlée d'un cache existant |
| Microsoft | **Application (client) ID** et choix des comptes admis | `MICROSOFT_CLIENT_ID`, `MICROSOFT_AUTHORITY` | Migration contrôlée d'un cache MSAL existant ; pas encore de commande initiale personnelle dédiée |

Une clé API Google, un mot de passe d'application, un certificat ou un secret de client Microsoft ne remplace pas ces éléments. Le code utilise un client Google installé et `msal.PublicClientApplication`, pas un flux de serveur à secret confidentiel ni des permissions d'application sans utilisateur.

### Retrouver les identifiants Job Tracker

Après création du connecteur dans l'interface, l'exploitant peut retrouver les numéros pour un apprenant précis. Avec la fonction `jt` du guide de déploiement :

```bash
# Remplacer l'adresse de connexion Job Tracker, pas par une adresse de boîte différente.
jt -c 'import sys; from app.database import get_connection
with get_connection() as db:
    rows = db.execute("SELECT i.user_id, i.id AS account_id, i.provider, i.email FROM imap_accounts i JOIN users u ON u.id=i.user_id WHERE u.email=? ORDER BY i.id", (sys.argv[1].strip().casefold(),)).fetchall()
    for row in rows:
        print(dict(row))' apprenant@campus.example
```

Cette lecture affiche les seuls identifiants, fournisseur et adresse des connecteurs du compte demandé, jamais les mots de passe ni les caches. Si aucune ligne ne sort, vérifier l'adresse de connexion et la création du connecteur ; ne pas choisir un numéro arbitraire.

## 1. Google : créer la configuration OAuth du Campus

### Projet et consentement

Dans la [console Google Cloud](https://console.cloud.google.com/), sélectionner ou créer un projet géré par le Campus, puis activer **Gmail API**. Job Tracker utilise IMAP pour lire les messages et Gmail API pour vérifier l'identité autorisée.

Dans **Google Auth Platform**, configurer le nom de l'application, le contact d'assistance et l'audience. Choisir **Internal** uniquement si l'organisation Workspace et les utilisateurs concernés le permettent ; sinon choisir **External**. En mode de test, ajouter les adresses des personnes qui feront la recette aux utilisateurs de test. Une simple page de consentement ne donne aucun accès aux boîtes. [Configuration du consentement](https://developers.google.com/workspace/guides/configure-oauth-consent).

Dans les accès aux données, prévoir le scope utilisé par le connecteur :

```text
https://mail.google.com/
```

Ce scope IMAP est large : il n'est pas limité à la lecture. Job Tracker ouvre les dossiers en lecture seule et n'envoie pas de candidature, mais cela ne réduit pas les droits du jeton. Ne pas remplacer ce scope par `gmail.readonly` sans modifier le connecteur : ce dernier scope concerne Gmail API et ne remplace pas l'autorisation IMAP actuelle. Une diffusion publique peut nécessiter la vérification Google ; le passage en production ne garantit pas son approbation. Le Campus doit valider ce point avant généralisation. [Scope IMAP officiel](https://developers.google.com/workspace/gmail/imap/xoauth2-protocol).

Pour une application **External / Testing** utilisant cet accès aux emails, Google indique que les refresh tokens expirent après sept jours. Ce mode convient à la recette, pas à une synchronisation durable annoncée comme opérationnelle. [Expiration des autorisations Google](https://developers.google.com/identity/protocols/oauth2#expiration).

### Client et fichier JSON

Dans **Clients**, créer un **OAuth client ID**, type **Desktop app / Application de bureau**, puis télécharger son JSON. C'est le format attendu par `InstalledAppFlow` dans `authorize_gmail.py` ; il ne faut pas choisir un client Web avec une route de callback inventée. [Création d'identifiants Google](https://developers.google.com/workspace/guides/create-credentials#desktop-app).

Sur le serveur préparé selon le [guide de déploiement](DEPLOIEMENT_PRODUCTION.md), transférer ce fichier par un canal administratif protégé, puis l'installer :

```bash
# Adapter uniquement le chemin du fichier téléchargé.
sudo install -o root -g jobtracker -m 0640 /chemin/vers/client-google.json /etc/jobtracker/google-client.json
sudoedit /etc/jobtracker/jobtracker.env
```

Configurer :

```dotenv
GMAIL_CREDENTIALS_FILE=/etc/jobtracker/google-client.json
```

Sur une installation locale, renseigner ce chemin dans `.env`. Ce JSON configure le client OAuth ; il ne constitue pas l'autorisation d'une boîte. Le fichier de jeton personnel sera créé séparément. Le déroulé Google est également illustré dans son [guide Python](https://developers.google.com/workspace/gmail/api/quickstart/python), mais les scopes et le stockage à utiliser ici sont ceux de Job Tracker.

### Autoriser une boîte Gmail

1. L'apprenant crée sa boîte dans **Mes connecteurs**, fournisseur **Gmail**, méthode **OAuth2**, TLS direct, port **993**, serveur `imap.gmail.com`, dossier `INBOX`. L'adresse et l'identifiant doivent correspondre à la même boîte.
2. L'exploitant relève le **user_id Job Tracker** et l'**id du compte IMAP**. Ils ne sont ni le client ID Google ni l'adresse email. Ne pas supposer qu'un numéro d'exemple correspond à la production.
3. Depuis la racine locale :

   ```bash
   # Remplacer 12 et 34 par les identifiants vérifiés.
   .venv/bin/python authorize_gmail.py --user-id 12 --account-id 34
   ```

   Sur le serveur, avec la fonction `jt` définie dans le guide de déploiement :

   ```bash
   jt authorize_gmail.py --user-id 12 --account-id 34
   ```

4. Ouvrir le lien affiché et autoriser **la boîte du connecteur**, pas le compte personnel de l'administrateur. Le script attend au maximum 180 secondes le retour du navigateur.
5. Attendre le message **Autorisation Gmail enregistrée après vérification de l'identité**. Le script vérifie le profil Google avant d'enregistrer le cache et n'importe aucun email. En cas de mauvaise identité ou d'échec, le cache existant n'est pas remplacé.

L'autorisation utilise un retour sur `127.0.0.1` avec un port choisi au lancement. Si le script tourne sur le serveur et le navigateur sur le poste de l'exploitant, préparer dans un second terminal un tunnel SSH vers **le port figurant dans l'URL de retour**. Exemple pour un port fictif 51234 :

```bash
ssh -N -L 127.0.0.1:51234:127.0.0.1:51234 administrateur@serveur-campus
```

Remplacer les deux occurrences du port par le port réel, puis ouvrir le lien d'autorisation avant expiration. Le tunnel reste ouvert jusqu'au retour OAuth. Ne pas publier ce port sur Internet ; il n'est pas une nouvelle route Nginx. Si le délai expire, relancer la commande et utiliser le nouveau port. L'autre possibilité est un navigateur sur la même machine que la commande. Le script utilise les retours locaux des applications installées, pas un consentement Web intégré à Job Tracker.

## 2. Microsoft : enregistrer l'application du Campus

### Identifiant et audience

Dans le [centre d'administration Microsoft Entra](https://entra.microsoft.com/), ouvrir **App registrations / Inscriptions d'applications → New registration**. Donner un nom explicite, par exemple « Job Tracker Campus ».

Choisir les comptes admis selon le périmètre réel : un seul tenant pour les comptes internes, plusieurs tenants pour plusieurs organisations, ou organisations **et comptes Microsoft personnels** si Outlook.com/Hotmail/Live/MSN doivent être acceptés. Copier l'**Application (client) ID** ; le Directory (tenant) ID est un autre identifiant. [Inscription d'une application](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app).

Dans **Authentication**, le parcours administratif d'autorisation doit être configuré comme client public. Pour un flux interactif de bureau, ajouter la plateforme **Mobile and desktop applications** et la redirection `http://localhost`. Un flux par code d'appareil demanderait sa configuration de client public et un outil adapté ; il n'est pas ajouté par ce guide. Ne pas créer de client secret pour tenter de le fournir à `PublicClientApplication`. [Configuration d'une application de bureau](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-desktop-app-sign-in).

### Permissions de la boîte

Dans **API permissions**, sélectionner l'API **Office 365 Exchange Online** et la permission **déléguée** `IMAP.AccessAsUser.All`. Selon la présentation de la console, chercher cette API dans les API utilisées par l'organisation. Le scope demandé par le connecteur est exactement :

```text
https://outlook.office.com/IMAP.AccessAsUser.All
```

L'autorisation renouvelable nécessite également l'accès hors ligne (`offline_access`) dans le flux d'acquisition géré par l'outil MSAL. `Microsoft Graph / Mail.Read` ne remplace pas cette permission Exchange IMAP. Ne pas ajouter `SMTP.Send`, de permission d'envoi ou de permission applicative `IMAP.AccessAsApp` : le connecteur actuel utilise un accès délégué au titulaire de la boîte. Obtenir le consentement administrateur si les règles du tenant l'exigent et vérifier que la boîte autorise IMAP. [Authentification OAuth IMAP Microsoft](https://learn.microsoft.com/en-us/exchange/client-developer/legacy-protocols/how-to-authenticate-an-imap-pop-smtp-application-by-using-oauth).

### Configurer Job Tracker

Dans le fichier d'environnement commun aux services :

```dotenv
MICROSOFT_CLIENT_ID=IDENTIFIANT_APPLICATION_DU_CAMPUS
MICROSOFT_AUTHORITY=https://login.microsoftonline.com/common
```

Le client ID n'est pas un secret de connexion. L'authority doit correspondre à l'audience enregistrée : `common` accepte les catégories de comptes autorisées par une application prévue pour organisations et particuliers ; pour une application interne à un tenant, utiliser `https://login.microsoftonline.com/IDENTIFIANT_TENANT`. Ne pas élargir l'audience sans besoin. [Types de comptes et authority](https://learn.microsoft.com/en-us/entra/identity-platform/msal-client-application-configuration).

Créer le connecteur personnel Microsoft avec OAuth2, TLS direct, serveur `outlook.office365.com`, port **993**, dossier `INBOX` et l'adresse exacte de la boîte comme identifiant.

### Première autorisation : limite de cette version

**Le dépôt ne fournit pas encore `authorize_microsoft.py` ni de bouton de consentement Microsoft Web.** Définir `MICROSOFT_CLIENT_ID` et créer le connecteur ne fabrique pas un cache MSAL. Le code actuel ne fait qu'ouvrir le cache privé et renouveler silencieusement l'accès du compte correspondant.

Pour une boîte sans cache, l'équipe technique doit donc préparer un parcours administratif personnel d'acquisition MSAL et de persistance du cache, ou faire implémenter cette étape avant d'annoncer la prise en charge de nouvelles boîtes Microsoft. Un tel parcours devra vérifier l'identité, demander uniquement les permissions prévues et enregistrer le cache pour le bon propriétaire/compte, sans afficher les jetons. La [documentation MSAL Python](https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens) décrit les flux possibles ; elle n'est pas une commande déjà intégrée à Job Tracker.

Si un **cache MSAL existant et compatible** est disponible, la migration de la section suivante est le parcours fourni. Un simple access token copié dans un fichier JSON n'est pas un cache `SerializableTokenCache` et ne suffit pas à la synchronisation durable. Un cache produit avec une autre application ou des autorisations incompatibles peut nécessiter un nouveau consentement.

## 3. Importer un ancien cache de manière contrôlée

Cette section s'applique seulement si un cache personnel existe déjà. Les chemins ci-dessous désignent les **sources de migration**, pas le stockage courant des nouveaux scans :

```dotenv
GMAIL_TOKEN_FILE=/var/lib/jobtracker/legacy/google-token.json
MICROSOFT_TOKEN_CACHE_FILE=/var/lib/jobtracker/legacy/microsoft-cache.json
```

Protéger le dossier de préparation (0700) et les fichiers (0600), avec accès par `jobtracker`. Préparer **une seule boîte à la fois**, arrêter le worker pendant la migration et vérifier le propriétaire et l'identifiant du compte dans la base cible. Le cache source doit contenir la bonne identité ; pour Microsoft, le migrateur exige exactement un compte.

Avec les identifiants fictifs 12 et 34 remplacés par les bons identifiants :

```bash
# Simulation : contrôle de la cible et du format ; ne prouve pas la validité réelle.
jt -m migrate.migrate_oauth_tokens --user-id 12 --account-id 34 --provider microsoft
# Après revue de la simulation, vérification réseau et copie explicites :
jt -m migrate.migrate_oauth_tokens --user-id 12 --account-id 34 --provider microsoft --apply
```

Pour Google, remplacer `microsoft` par `gmail`. Sur le poste local, remplacer `jt` par `.venv/bin/python`. La commande `--apply` demande `MIGRER`, contrôle réellement l'identité, conserve la source et refuse d'écraser un cache privé déjà présent. Ne pas renommer arbitrairement un cache sous un autre identifiant pour contourner ce refus. Une nouvelle autorisation ou révocation doit être traitée séparément.

Les caches courants sont enregistrés sous :

```text
DATABASE_PATH.parent/oauth/users/<user_id>/accounts/<account_id>/gmail_token.json
DATABASE_PATH.parent/oauth/users/<user_id>/accounts/<account_id>/microsoft_cache.json
```

Ils contiennent des secrets donnant accès à la boîte. Ne pas les versionner, les envoyer par email ni les joindre à un ticket ; leur sauvegarde doit être protégée comme les données de messagerie. Un JSON de client Google configure l'application, un cache autorise une boîte : ils ne sont pas interchangeables.

## 4. Activer et vérifier la synchronisation

Après modification du fichier d'environnement, redémarrer **le Web et le worker** pour qu'ils chargent la même configuration. Un renouvellement de cache seul ne change pas les paramètres chargés au démarrage ; le scan suivant relit le fichier privé.

1. Le titulaire se connecte à son compte Job Tracker.
2. Dans **Mes connecteurs**, vérifier que sa boîte est active et lancer **Tester la connexion**. Le travail doit réussir sans importer de message ni modifier le checkpoint.
3. Lancer un seul scan et consulter **Mes travaux** : comptes analysés, emails importés et éventuelles erreurs de checkpoint.
4. Faire un second scan pour vérifier l'absence de doublons. Tester également la reconnexion ultérieure après expiration naturelle d'un access token, sans réautoriser artificiellement à chaque scan.

L'existence d'un fichier ou un test réussi aujourd'hui ne garantit pas la validité future du consentement. En cas d'échec, vérifier audience/client ID, identité de boîte, permissions, politiques de l'organisation et accès IMAP avant de toucher au cache. En cas de révocation, refaire une autorisation personnelle ; ne pas supprimer tous les caches des apprenants.

## Éléments à transmettre à l'exploitant

- Le projet Google, son responsable, l'audience/état de publication et le JSON client installé au bon chemin.
- L'application Entra, son client ID, son tenant/audience, l'authority et les permissions consenties.
- La procédure d'autorisation de chaque boîte, les identifiants Job Tracker/IMAP vérifiés et la procédure de révocation.
- La couverture de sauvegarde des caches, leur contrôle d'accès et la recette réelle par fournisseur.
- La limite actuelle sur la première autorisation Microsoft, à lever avant l'accueil autonome de nouvelles boîtes Microsoft.

Ce guide décrit la préparation ; aucune application fournisseur, autorisation réelle ou synchronisation personnelle n'a été créée pendant sa rédaction.
