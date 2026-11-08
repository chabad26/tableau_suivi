# Présenter la gestion des connecteurs personnels

Cette évolution est intégrée dans `integration/campus-finalisation`, issue de `feature/demo-campus-finalisation` et fusionnée avec `feature/connecteurs-campus`. Les contrôles de synchronisation et le mode hors ligne sont conservés.

## Ouvrir la page

Après installation des dépendances, depuis la racine :

```bash
.venv/bin/python web.py
```

Se connecter avec son compte utilisateur, puis cliquer **Connecteurs** sur le tableau, ou ouvrir http://127.0.0.1:5000/connectors.

Pour exécuter les tests de connexion demandés depuis l'interface, lancer dans un autre terminal :

```bash
.venv/bin/python worker.py
```

Le worker peut également traiter les scans personnels déjà en file. Pour une présentation sans fournisseur réel, utiliser les tests automatisés ci-dessous et une base de présentation séparée ; ne pas demander de connexion sur une messagerie réelle.

## Parcours de présentation

1. **Mes connecteurs** affiche uniquement les boîtes de l'utilisateur connecté, leur fournisseur, serveur, dossier, type d'authentification, activation et dernier résultat connu. Un résultat ancien n'est pas présenté comme une garantie de connexion actuelle.
2. **Ajouter une boîte mail** : détection facultative du fournisseur ou saisie manuelle. Pour une démonstration sans DNS, utiliser une adresse réservée comme `alice-mail@campus.invalid`, choisir **Autre fournisseur IMAP** et saisir `imap.campus.invalid`. Le gestionnaire de secrets système doit être disponible pour enregistrer une boîte par mot de passe.
3. Choisir un fournisseur connu préremplit le serveur et le port et sélectionne l'authentification correspondante. Les formulaires indiquent TLS direct ou STARTTLS obligatoire. Les mots de passe passent au gestionnaire de secrets, jamais dans SQLite ni dans le HTML de modification.
4. **Modifier** : laisser le mot de passe vide conserve le secret actuel, sauf changement d'identité exigeant un nouveau mot de passe. Une configuration inchangée conserve le checkpoint ; un changement de configuration réinitialise UID et UIDVALIDITY pour éviter de sauter des messages. Les emails et candidatures ne sont pas supprimés.
5. **Désactiver / Activer** conserve la boîte, son historique et son checkpoint. Une boîte désactivée ne peut pas être testée.
6. **Tester la connexion** enregistre un job personnel et ouvre **Mes travaux**. Le worker vérifie connexion, authentification et accès au dossier en lecture seule. Il ne parcourt pas les messages, n'importe rien et n'avance pas le checkpoint. Actualiser pour voir le résultat.
7. Avec une session d'un second utilisateur, les boîtes et les jobs du premier ne sont pas affichés. Les URL d'édition, de test et d'activation d'autrui renvoient 404.

## Limite OAuth à annoncer clairement

La création d'une configuration Gmail/Microsoft n'effectue pas une nouvelle autorisation OAuth interactive. La page indique si un cache personnel existe, sans lire son contenu ; son existence ne prouve pas sa validité. Une autorisation OAuth personnelle valide doit déjà être configurée par le parcours administratif existant pour que le test réussisse. Le bouton de test ne lance pas un nouvel écran de consentement.

Les anciens caches ne sont ni migrés ni renouvelés par cette évolution. Aucun véritable jeton n'a été lu ou modifié pendant sa validation. Les chemins OAuth sont séparés par utilisateur et compte, comme dans la branche de finalisation. Les anciens caches ne sont pas utilisés automatiquement ; une copie contrôlée ou une nouvelle autorisation est nécessaire.

## Contrôles conservés

- Le propriétaire provient de la session et n'est jamais choisi depuis le formulaire.
- Les requêtes de lecture/écriture qualifient le compte par `user_id` ; les jobs possèdent le même propriétaire.
- Tous les POST sont protégés par CSRF. La connexion est requise pour les pages personnelles.
- Une empreinte des paramètres du formulaire détecte une configuration devenue différente ; l'édition et l'activation sont refusées pendant un scan personnel ou un test utilisant cette boîte.
- Les échecs du keyring annulent les paramètres SQLite ; un gestionnaire de secrets externe ne partage pas la transaction SQLite et doit être vérifié si son résultat est incertain.
- Les erreurs techniques brutes ne sont affichées ni dans la page ni dans les jobs. Les détails historiques `last_error` ne sont pas rendus dans l'interface.
- Le schéma existant conserve l'unicité globale des adresses IMAP : un conflit est refusé sans révéler l'autre propriétaire.
- Les jobs historiques sans propriétaire restent ignorés par le worker personnel.
- Sur cette branche, les exports et les autres actions non migrées restent bloqués ; le scan personnel `/scan` est réactivé. Les tests de connexion et la [réanalyse personnelle des archives](REANALYSE.md) sont disponibles dans la file des jobs personnels.

## Validation hors réseau

```bash
.venv/bin/ruff format .
.venv/bin/ruff check .
npx --yes pyright
node --check static/imap-form.js
.venv/bin/python -m unittest discover -s tests -v
```

Les nouveaux tests utilisent SQLite temporaire, un keyring simulé et des connexions IMAP simulées. Ils couvrent création, modification, activation, conflits, CSRF, isolation, déduplication des jobs et absence de lecture d'emails pendant un test de connexion. Aucun test ne lance de synchronisation réelle. Le test IMAP historique a été isolé sur une base temporaire pour ne plus initialiser la base habituelle.

Contrôle initial de la gestion des connecteurs : **233 tests réussis**, Ruff conforme, Pyright sans erreur ni avertissement et JavaScript valide avec `node --check`. Le rendu des pages et les formulaires ont été vérifiés avec le client de test Flask ; aucune connexion réelle à un fournisseur n'avait été lancée pendant ce contrôle initial.

## Renouveler une autorisation Gmail refusée

L'expiration du jeton d'accès est normale. Si Google refuse son renouvellement, une nouvelle autorisation peut être nécessaire. Les diagnostics OAuth Gmail contrôlés sont conservés par le scanner, les tests de connexion, les logs du worker et la page des travaux. Les erreurs techniques inattendues restent masquées ; un test de connexion indique seulement l'étape concernée (connexion/TLS, authentification/OAuth ou dossier).

Depuis le terminal local, arrêter le worker avec `Ctrl+C`, puis lancer, en remplaçant les identifiants par ceux du propriétaire et de sa boîte :

```bash
.venv/bin/python authorize_gmail.py --user-id 1 --account-id 3
```

Choisir dans le navigateur l'adresse Google qui correspond exactement au compte IMAP. Le consentement attend au maximum trois minutes. La commande exige une autorisation renouvelable et vérifie l'identité via le profil Gmail avant d'écrire le cache privé de cette seule boîte. Une erreur d'identité conserve le cache existant. Aucun email n'est lu ni importé ; les caches historiques et les autres fournisseurs ne sont pas modifiés. La commande suppose que le fichier client OAuth Google est déjà configuré.

Redémarrer ensuite le worker et demander un seul test de connexion Gmail depuis les connecteurs.
