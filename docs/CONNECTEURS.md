# Présenter la gestion des connecteurs personnels

Cette évolution part de `main` sur la branche `feature/connecteurs-campus`. Elle réactive la gestion des boîtes IMAP et les tests de connexion personnels. Elle ne fusionne pas automatiquement la branche de finalisation de la démonstration.

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

Les anciens caches ne sont ni migrés ni renouvelés par cette évolution. Aucun véritable jeton n'a été lu ou modifié pendant sa validation. Les chemins OAuth sont ceux du `main` de départ ; cette branche ne reprend pas le changement de chemin de la branche de finalisation précédente.

## Contrôles conservés

- Le propriétaire provient de la session et n'est jamais choisi depuis le formulaire.
- Les requêtes de lecture/écriture qualifient le compte par `user_id` ; les jobs possèdent le même propriétaire.
- Tous les POST sont protégés par CSRF. La connexion est requise pour les pages personnelles.
- Une empreinte des paramètres du formulaire détecte une configuration devenue différente ; l'édition et l'activation sont refusées pendant un scan personnel ou un test utilisant cette boîte.
- Les échecs du keyring annulent les paramètres SQLite ; un gestionnaire de secrets externe ne partage pas la transaction SQLite et doit être vérifié si son résultat est incertain.
- Les erreurs techniques brutes ne sont affichées ni dans la page ni dans les jobs. Les détails historiques `last_error` ne sont pas rendus dans l'interface.
- Le schéma existant conserve l'unicité globale des adresses IMAP : un conflit est refusé sans révéler l'autre propriétaire.
- Les jobs historiques sans propriétaire restent ignorés par le worker personnel.
- Sur cette branche, `/scan`, les exports et les autres actions non migrées restent bloqués. Les tests de connexion et la [réanalyse personnelle des archives](REANALYSE.md) sont disponibles dans la file des jobs personnels.

## Validation hors réseau

```bash
.venv/bin/ruff format .
.venv/bin/ruff check .
npx --yes pyright
node --check static/imap-form.js
.venv/bin/python -m unittest discover -s tests -v
```

Les nouveaux tests utilisent SQLite temporaire, un keyring simulé et des connexions IMAP simulées. Ils couvrent création, modification, activation, conflits, CSRF, isolation, déduplication des jobs et absence de lecture d'emails pendant un test de connexion. Aucun test ne lance de synchronisation réelle. Le test IMAP historique a été isolé sur une base temporaire pour ne plus initialiser la base habituelle.

Dernier contrôle local : **171 tests réussis**, Ruff conforme, Pyright sans erreur ni avertissement et JavaScript valide avec `node --check`. Le rendu des pages et les formulaires ont été vérifiés avec le client de test Flask ; aucune connexion réelle à un fournisseur n'a été lancée.
