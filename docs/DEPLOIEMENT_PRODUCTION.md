# Déployer Job Tracker Campus en production

Ce guide s'adresse à la personne qui reprendra l'exploitation. Il fournit des modèles pour **un serveur Linux, une instance de l'application et un disque local**, derrière Nginx en HTTPS. Le code utilise Python **3.14** et des verrous `fcntl` ; ne pas transposer directement vers Windows ou un hébergement mutualisé ne permettant ni worker persistant ni services système.

Les modèles sont préparés dans le dépôt ; ils ne constituent pas la preuve d'un déploiement. Aucun serveur distant, DNS, certificat, compte réel ou jeton personnel n'a été modifié pendant leur préparation. Le domaine `candidatures.example.org` est fictif et doit être remplacé partout.

## 1. Architecture et prérequis

Navigateur → Nginx HTTPS → Gunicorn sur `127.0.0.1:8000` → Flask/SQLite. Un second service exécute `worker.py` pour les tests IMAP, scans et réanalyses. La connexion Web met les travaux en file sans attendre Internet. Sans worker, les pages restent accessibles mais les travaux ne sont pas exécutés.

Prévoir une machine Linux maintenue avec systemd, Python 3.14 et son module `venv`, Git, Nginx, une autorité de certificats et l'accès administratif. La disponibilité de Python 3.14 dépend de la distribution : utiliser une installation maintenue, sans remplacer le Python système. Le guide suppose que `python3.14` est disponible. Node/npm et les dépendances de développement ne sont nécessaires que pour les contrôles de développement.

Le pare-feu autorise HTTPS, HTTP si nécessaire pour redirection/certificats, et SSH depuis les postes d'administration. Le port 8000 reste local. Les scans demandent DNS, HTTPS sortant pour OAuth et IMAP TLS vers les serveurs configurés (généralement 993 ou STARTTLS 143). Ne pas ouvrir de port IMAP entrant sur le serveur applicatif.

| Emplacement | Contenu | Accès prévu |
| --- | --- | --- |
| `/opt/jobtracker` | Code et environnement Python | root écrit, compte de service lit/exécute |
| `/etc/jobtracker/jobtracker.env` | Configuration et clé des sessions | root écrit, groupe `jobtracker` lit, 0640 |
| `/etc/jobtracker/google-client.json` | Client OAuth Google si utilisé | root écrit, groupe `jobtracker` lit, 0640 |
| `/var/lib/jobtracker/job_tracker.db` | Comptes, candidatures, emails, travaux, métadonnées CV/LM | `jobtracker`, dossier 0700 |
| `/var/lib/jobtracker/documents/` | Fichiers privés des documents et versions | `jobtracker`, dossiers 0700/fichiers 0600 |
| `/var/lib/jobtracker/oauth/users/…/accounts/…/` | Caches OAuth personnels | `jobtracker`, dossiers 0700/fichiers 0600 |
| Trousseau système | Mots de passe IMAP, service `job-tracker-imap` | Même backend pour le Web et le worker |

Ne pas placer SQLite sur un partage réseau ni lancer plusieurs instances sur plusieurs machines avec cette configuration. Un seul worker de travaux utilise la base. Le modèle Gunicorn démarre un processus Web avec quatre threads, distinct du worker IMAP ; c'est un point de départ à mesurer, sans promesse de capacité. Une montée en charge demande des tests et éventuellement une autre base/file.

## 2. Installer le code

Commandes destinées au **nouveau serveur**, pas au poste personnel. Choisir un commit revu contenant les évolutions souhaitées, et conserver sa référence pour les mises à jour.

```bash
sudo useradd --system --user-group --home-dir /var/lib/jobtracker --shell /usr/sbin/nologin jobtracker
sudo install -d -o jobtracker -g jobtracker -m 0700 /var/lib/jobtracker
sudo install -d -o root -g jobtracker -m 0750 /etc/jobtracker
sudo git clone https://github.com/chabad26/tableau_suivi.git /opt/jobtracker
cd /opt/jobtracker
# Remplacer COMMIT_VALIDE par la référence réellement validée.
sudo git checkout --detach COMMIT_VALIDE
sudo python3.14 -m venv /opt/jobtracker/.venv
sudo /opt/jobtracker/.venv/bin/python -m pip install -r /opt/jobtracker/requirements-prod.txt
sudo /opt/jobtracker/.venv/bin/python -m pip check
```

`requirements-prod.txt` inclut les dépendances applicatives et Gunicorn, sans les outils de développement. Les dépendances transitives ne sont pas toutes verrouillées : conserver aussi le résultat de `pip freeze` pour reproduire une installation. Ne pas installer un paquet Python global avec pip.

## 3. Configurer avant tout démarrage

```bash
sudo install -o root -g jobtracker -m 0640 deploy/jobtracker.env.example /etc/jobtracker/jobtracker.env
sudoedit /etc/jobtracker/jobtracker.env
```

Choisir la date de début de scan selon le périmètre souhaité : une date trop ancienne peut provoquer un import initial volumineux. `APPLICATION_EXPIRY_DAYS` règle le passage « Sans réponse ». Les chemins sont absolus. Les variables de processus priment sur `.env` ; **ne pas copier le `.env` personnel dans le code de production**. L'environnement systemd est commun aux deux services et aux commandes ci-dessous.

Générer la clé de session directement dans le fichier, sans l'afficher :

```bash
sudo /opt/jobtracker/.venv/bin/python - <<'PY'
from pathlib import Path
import secrets
path = Path('/etc/jobtracker/jobtracker.env')
text = path.read_text()
placeholder = 'REMPLACER_PAR_UNE_CLE_ALEATOIRE_PERSISTANTE'
if text.count(placeholder) != 1:
    raise SystemExit('Clé déjà configurée ou modèle inattendu : aucune modification.')
path.write_text(text.replace(placeholder, secrets.token_hex(32)))
PY
```

`APP_HTTPS=true` active le cookie `Secure` : accéder au site public en HTTPS. Il ne crée pas de certificat. Garder la même clé lors des redémarrages ; sa rotation déconnecte les sessions. La clé ne chiffre ni SQLite ni les caches OAuth. Ne pas versionner ces fichiers ni les communiquer dans un ticket.

Le modèle ne configure pas `ProxyFix` : l'application utilise des redirections relatives et ne doit pas faire confiance automatiquement à des en-têtes fournis par un client. Si une future fonctionnalité demande des URL absolues externes, configurer explicitement la confiance dans l'unique proxy contrôlé.

## 4. Commandes d'administration et initialisation

Pour exécuter les commandes avec **le même utilisateur et le même fichier d'environnement** que les services, définir cette fonction dans le terminal de l'administrateur du serveur :

```bash
jt() {
    sudo systemd-run --wait --pty --collect \
        --property=User=jobtracker --property=Group=jobtracker \
        --property=WorkingDirectory=/opt/jobtracker \
        --property=EnvironmentFile=/etc/jobtracker/jobtracker.env \
        --property=UMask=0077 --property=Environment=PYTHONDONTWRITEBYTECODE=1 \
        /opt/jobtracker/.venv/bin/python "$@"
}
```

Cette fonction utilise un service transitoire et un terminal pour les saisies de mot de passe. Elle n'exporte pas les secrets dans le shell. Sur une machine sans terminal, ne pas transformer les mots de passe en arguments de commande : effectuer cette étape dans une session administrative interactive.

Pour une base neuve :

```bash
jt -c 'from app.web import create_app; create_app(); print("Schéma initialisé")'
jt create_account.py admin@votre-domaine.fr --role admin
jt -m migrate.migrate_email_uniqueness
jt -m migrate.migrate_email_uniqueness --apply
```

Remplacer l'adresse administrative. Le mot de passe est saisi deux fois sans affichage, avec 12 caractères minimum. La dernière commande demande `MIGRER` pour remplacer l'unicité globale des Message-ID par `(user_id, message_id)` ; même une base neuve doit passer par cette étape. Le mode sans `--apply` effectue les vérifications sans migration. Une sauvegarde SQLite est créée par le script lors de l'application.

**Si la base existe déjà**, faire d'abord la sauvegarde de la section 8, arrêter Web et worker, puis initialiser le schéma et examiner les migrations sur une copie. Les ajouts de colonnes/tables sont automatiques ; l'attribution des anciennes données ne l'est pas. L'initialisation convertit également les anciens statuts `SENT` des candidatures et emails vers `RECEIVED`, sans toucher aux notes ni aux dates et sans créer de changement historique fictif. Les événements historiques bruts restent intacts ; leurs compteurs sont regroupés dans « Reçue ». Les scripts `migrate_legacy_data`, `migrate_imap_accounts`, `migrate_oauth_tokens` sont réservés aux cas historiques concernés : lire leur aide et leur procédure, contrôler les propriétaires, ne pas attribuer automatiquement toutes les anciennes données à un nouvel administrateur. Voir [l'intégration](INTEGRATION.md) et [la sécurité](SECURITE.md).

## 5. Préparer les secrets de messagerie

L'installation Web et les documents fonctionnent sans connecter de boîte. La création d'un connecteur n'autorise pas automatiquement Google ou Microsoft.

### Comptes avec mot de passe

Le code appelle `keyring` sous le service `job-tracker-imap`, avec l'identifiant IMAP comme clé. Un trousseau de session du poste personnel n'est pas automatiquement disponible sur un serveur. Le Web doit pouvoir écrire le secret, et le worker le relire sous `jobtracker` après redémarrage.

Sur Linux sans bureau, Secret Service nécessite un daemon de trousseau déverrouillé et une session D-Bus **commune aux deux services**. L'exploitant doit préparer ce backend, sa méthode de déverrouillage et sa sauvegarde avant d'activer des boîtes avec mot de passe. Les modèles systemd ne le créent pas. Les éventuels paramètres `DBUS_SESSION_BUS_ADDRESS`, `XDG_RUNTIME_DIR` et backend doivent désigner le service réellement provisionné et être présents dans le contexte des deux processus. Un backend tiers peut demander ses propres paquets et droits ; les restrictions systemd doivent être adaptées précisément si nécessaire.

Vérifier la classe du backend dans chaque contexte, sans afficher de secret :

```bash
jt -c 'import keyring; k=keyring.get_keyring(); print(type(k).__module__, type(k).__name__)'
```

Ce contrôle ne prouve pas que le trousseau est déverrouillé. La recette finale consiste à créer un compte fictif de test dans le trousseau, vérifier lecture/suppression sans imprimer la valeur, redémarrer les services puis tester une boîte autorisée depuis les connecteurs. Un backend nul, défaillant ou un fichier en clair n'est pas une solution de production. Ne pas stocker ces mots de passe dans les unités systemd ou la base pour contourner le problème. La copie de SQLite seule ne transfère pas les secrets.

### OAuth Gmail et Microsoft

Installer le client Google adapté dans `/etc/jobtracker/google-client.json` si Gmail est utilisé, puis renseigner `MICROSOFT_CLIENT_ID` si nécessaire. Les caches personnels sont isolés par utilisateur et compte sous le dossier de données ; leur présence ne prouve pas leur validité.

`authorize_gmail.py --user-id … --account-id …` fournit le parcours explicite Gmail avec vérification de l'identité. Il écoute un retour OAuth sur **127.0.0.1 et un port dynamique** : ouvrir son URL sur un autre poste ne redirige pas automatiquement vers le serveur. Préparer un accès navigateur sur la machine autorisante ou une procédure d'autorisation/transfert contrôlée avec les mêmes identifiants et vérification de l'identité. Ne pas exposer ce serveur de retour sur Internet. Le consentement OAuth Web pour les apprenants n'est pas implémenté.

Pour les anciens caches, `jt -m migrate.migrate_oauth_tokens --user-id … --account-id … --provider gmail` (ou `microsoft`) simule les vérifications de format et de cible. `--apply` demande confirmation et vérifie réellement l'identité avant copie ; il conserve l'original et refuse d'écraser un cache privé existant. Microsoft ne dispose pas ici d'une nouvelle commande d'autorisation personnelle équivalente à celle de Gmail : prévoir son parcours administratif séparé avant d'annoncer ce connecteur opérationnel. Ne pas lancer les anciens flux globaux pour connecter plusieurs apprenants.

Les appels des fournisseurs et les consentements réels nécessitent la validation de leurs configurations OAuth. Les scans du worker ne lancent pas de navigateur lorsqu'une autorisation manque : ils échouent, et l'utilisateur conserve l'accès à ses candidatures.

## 6. Installer les services et HTTPS

```bash
sudo install -m 0644 deploy/jobtracker-web.service /etc/systemd/system/
sudo install -m 0644 deploy/jobtracker-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now jobtracker-web.service jobtracker-worker.service
sudo systemctl status jobtracker-web.service jobtracker-worker.service
```

Le code reste en lecture seule, les écritures sont limitées à `/var/lib/jobtracker`, et l'UMask est 0077. Ces restrictions ne remplacent pas la recette du backend de secrets. Les deux services doivent partager la même base et la même clé. Aucun rechargement automatique du code, aucun mode debug ni `--preload` Gunicorn n'est activé.

Tester d'abord `curl -I http://127.0.0.1:8000/login` : une réponse HTTP prouve que le Web répond, pas que l'import mail fonctionne.

Choisir le domaine, créer son DNS et obtenir un certificat couvrant ce nom avec le mécanisme de l'hébergeur ou un client ACME maintenu. Installer et tester son renouvellement automatique. Le modèle TLS suppose **un certificat déjà disponible** aux chemins indiqués : ne pas l'activer avec des chemins inexistants. Pour une validation HTTP ACME, adapter la route du challenge selon le client ; aucun client ni renouvellement n'est installé par ces exemples.

```bash
sudo install -m 0644 deploy/nginx-jobtracker.conf /etc/nginx/sites-available/jobtracker
sudoedit /etc/nginx/sites-available/jobtracker
# Après remplacement du domaine et des chemins des certificats :
sudo ln -s /etc/nginx/sites-available/jobtracker /etc/nginx/sites-enabled/jobtracker
sudo nginx -t
sudo systemctl reload nginx
```

Ces chemins suivent l'organisation Debian/Ubuntu ; adapter si la distribution utilise `conf.d`. Éviter de créer deux liens si le site est déjà activé. Le modèle redirige HTTP vers le nom HTTPS explicite, limite la requête à 12 Mio et conserve la limite de 10 Mio du fichier côté Flask. Il ne publie **aucun dossier privé** avec `alias` ou `root`. Les ressources statiques sont servies par l'application pour ce premier déploiement.

Les endpoints de connexion ne disposent pas encore de limitation applicative du nombre de tentatives. Avant une ouverture large sur Internet, l'exploitant doit définir et tester la protection des connexions au niveau de son proxy/passerelle, selon le nombre d'apprenants partageant une adresse IP. Le modèle n'impose pas un quota arbitraire à tout le campus. L'inscription publique, la réinitialisation automatique du mot de passe et la double authentification ne sont pas disponibles dans cette version.

## 7. Recette sur le serveur

Effectuer ces contrôles avec des comptes de recette et des fichiers fictifs avant d'importer les données des apprenants :

1. HTTPS valide, HTTP redirigé, port 8000 non accessible depuis un autre poste ; cookies `HttpOnly`, `SameSite=Lax`, `Secure` observés après connexion.
2. Créer une promotion et deux apprenants dans le backoffice. Vérifier le cloisonnement des candidatures, emails, travaux et documents ; l'équipe pédagogique consulte les CV/LM et les chiffres, pas les candidatures privées d'autrui.
3. Déposer un petit PDF/DOCX, une nouvelle version, un message et une annotation ; télécharger depuis les deux profils autorisés. Tester un dépôt proche de 10 Mio puis un dépassement refusé. Ne pas tester avec un document personnel.
4. Vérifier le logo Campus et le footer Olidev, les mises en page mobile, le rendu des emails HTML avec images désactivées.
5. Vérifier la réanalyse hors réseau. Une indisponibilité du fournisseur ne doit pas bloquer la connexion ; le bandeau finit son suivi et les travaux gardent leur état réel. Sans worker, vérifier l'état d'attente puis redémarrer le worker.
6. Après préparation et autorisation des secrets, tester **une seule boîte autorisée**, puis un scan réel unique ; vérifier le résultat, l'import et les checkpoints, puis l'absence de doublon au scan suivant. C'est une opération réelle à planifier avec son propriétaire, pas un test automatisé du dépôt.
7. Sauvegarder, restaurer sur une instance de recette sans scans sortants, vérifier SQLite et télécharger un document ; ne pas lancer deux workers contre la production.

Suivi : `sudo journalctl -u jobtracker-web -u jobtracker-worker --since today`. Les traces peuvent contenir des identifiants de boîtes, des URL et des informations personnelles : réserver l'accès aux exploitants, définir la rétention, masquer ces éléments avant partage. Ne jamais copier le contenu des jetons ou un mot de passe dans un diagnostic. Les durées des scans, erreurs, file en attente, espace disque et expiration des certificats sont à surveiller. Il n'y a pas de quota cumulé de documents ni de purge automatique générale.

## 8. Sauvegarde cohérente

Sauvegarder ensemble **SQLite, ses fichiers annexes éventuels, `documents/`, `oauth/`, la configuration et le trousseau externe**. Définir la fréquence et la rétention selon les besoins du campus ; chiffrer et contrôler l'accès aux sauvegardes, conserver une copie sur un autre support. Les sauvegardes automatiques des scripts de migration ne couvrent pas tout ce périmètre.

Pour une copie locale cohérente, le modèle Nginx reconnaît le marqueur `/run/jobtracker-maintenance`. Pendant la sauvegarde, aucune commande administrative ne doit modifier les données. Dans un shell root sur le serveur :

```bash
sudo -i
touch /run/jobtracker-maintenance
systemctl stop jobtracker-web jobtracker-worker
systemctl is-active jobtracker-web jobtracker-worker
# Attendre l'état inactive des deux services avant de copier.
install -d -m 0700 /var/backups/jobtracker
snapshot=/var/backups/jobtracker/$(date -u +%Y%m%dT%H%M%SZ)
install -d -m 0700 "$snapshot"
cp -a /var/lib/jobtracker "$snapshot/data"
cp -a /etc/jobtracker "$snapshot/config"
git -C /opt/jobtracker rev-parse HEAD > "$snapshot/commit.txt"
/opt/jobtracker/.venv/bin/python -m pip freeze > "$snapshot/requirements.freeze.txt"
# Sauvegarder aussi le backend de secrets selon sa procédure propre.
```

Contrôler que la copie est complète et que le trousseau est couvert avant de redémarrer. Les fichiers de verrous OAuth/worker ne sont pas des secrets à déverrouiller en les supprimant : les verrous système sont libérés à l'arrêt des processus. Ne pas omettre les éventuels fichiers SQLite `-wal`, `-shm` ou `-journal` en copiant seulement le fichier `.db`.

```bash
systemctl start jobtracker-web jobtracker-worker
systemctl is-active jobtracker-web jobtracker-worker
# Après vérification des deux services et du Web local :
rm /run/jobtracker-maintenance
exit
```

Si la copie ou le redémarrage échoue, conserver la maintenance, examiner l'erreur et corriger avant de rouvrir. Le marqueur dans `/run` disparaît au redémarrage du serveur : ce n'est pas un mécanisme de maintenance persistant.

## 9. Mise à jour et retour arrière

1. Valider la révision cible dans une copie de développement : installation, Ruff/Pyright, suite Python et tests JavaScript. Ne pas lancer les tests en installant leurs outils dans le service de production.
2. Mettre en maintenance, arrêter les deux services et réaliser la sauvegarde complète de la section 8 ; garder la révision précédente et le manifeste de dépendances.
3. Dans `/opt/jobtracker`, récupérer la révision revue (`git fetch`, puis `git checkout --detach COMMIT_VALIDE`). Ne pas écraser des changements locaux sans les examiner.
4. Installer `requirements-prod.txt`, lancer `pip check`, puis initialiser le schéma avec `jt -c 'from app.web import create_app; create_app()'`. Appliquer uniquement les migrations nécessaires après simulation et contrôle des propriétaires. Ne jamais supposer qu'une ancienne version peut lire un nouveau schéma.
5. Redémarrer Web puis worker, contrôler les services, HTTPS, connexion, documents et travaux avec les comptes de recette. En cas de succès, retirer le marqueur de maintenance.

Pour revenir en arrière après modification de schéma ou fichiers : remettre la révision précédente et restaurer **tout le même instantané**, pas uniquement le code. La restauration perd les écritures postérieures à la sauvegarde ; décider du point de reprise avant de rouvrir aux apprenants.

Sur une instance arrêtée et en maintenance, conserver le dossier de données défaillant sous un autre nom, puis copier `snapshot/data` comme **nouveau** `/var/lib/jobtracker` (ne pas fusionner avec des WAL ou documents d'une autre version). Restaurer `snapshot/config` au bon emplacement, le trousseau associé, les permissions et les dépendances de la révision restaurée. Les UID/GID doivent correspondre au compte de service de la machine cible. Protéger également le dossier mis de côté.

Avant de redémarrer :

```bash
jt -c 'import sqlite3; from app.settings import DATABASE_PATH; db=sqlite3.connect(DATABASE_PATH.resolve().as_uri()+"?mode=ro", uri=True); print(db.execute("PRAGMA integrity_check").fetchall()); print(db.execute("PRAGMA foreign_key_check").fetchall()); db.close()'
```

Attendre `ok` pour l'intégrité et aucune ligne pour les clés étrangères. Ces contrôles SQLite ne vérifient pas les fichiers privés : télécharger ensuite un document de recette et vérifier les accès. Une copie de recette ne doit pas exécuter les scans ni renouveler les mêmes jetons que la production.

En cas de fichier `.deleting-…` après arrêt brutal, lire la [procédure documents](DOCUMENTS.md) et confronter le fichier à la version en base avant restauration ou suppression. Ne pas lancer un nettoyage global des fichiers privés.

## 10. Dépannage rapide

| Symptôme | Vérification et action |
| --- | --- |
| Nginx 502 | Service Web, journal, écoute locale 8000 ; ne pas ouvrir ce port publiquement |
| Nginx ne démarre pas | `nginx -t`, domaine et fichiers du certificat |
| Cookie de session absent | HTTPS, `APP_HTTPS=true`, clé commune persistante |
| Travaux en attente | Service worker, même `DATABASE_PATH`, verrou d'un autre worker |
| Scan partiel / RuntimeError | Résultat par compte et erreurs de checkpoint ; ne pas relancer en boucle |
| Mot de passe IMAP indisponible | Backend et déverrouillage du trousseau sous le compte de service, dans les deux processus |
| OAuth absent/expiré | Identité et compte ciblés, configuration client, procédure administrative ; aucun consentement automatique dans le Web |
| Dépôt refusé 413 | Limite Nginx 12 Mio, fichier Flask 10 Mio, marges multipart |
| Document indisponible | Même instantané base/fichiers, propriétaire, permissions, taille et empreinte ; ne pas contourner le contrôle d'intégrité |
| SQLite verrouillée | Autre processus, opération longue, disque local, un seul worker ; ne pas supprimer un verrou au hasard |

## Références et limites de validation

Les modèles s'appuient sur la [documentation Flask pour Gunicorn](https://flask.palletsprojects.com/en/stable/deploying/gunicorn/), les [directives Nginx](https://nginx.org/en/docs/http/ngx_http_core_module.html#client_max_body_size), les [options d'exécution systemd](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html) et la [préparation de keyring sans bureau](https://keyring.readthedocs.io/en/latest/#using-keyring-on-headless-linux-systems). La version Gunicorn du fichier de production est choisie depuis sa [distribution officielle](https://pypi.org/project/gunicorn/).

Les contrôles locaux du guide sont consignés dans le [suivi des lots](EVOLUTIONS_CAMPUS.md#lot-8-deploiement-et-exploitation). Ils ne prouvent ni la configuration TLS du futur hébergeur, ni un backend de secrets déverrouillé, ni un scan réel, ni la bonne restauration des futures sauvegardes. Ces points font partie de la recette de l'exploitant.
