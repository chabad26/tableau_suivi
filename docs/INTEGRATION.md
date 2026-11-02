# Intégration Campus : résultat vérifié

Contrôle du 2 novembre 2026 sur la branche `integration/campus-finalisation`, créée depuis `feature/demo-campus-finalisation`, puis fusionnée avec `feature/connecteurs-campus`.

## Résolution des conflits

La fusion conserve les deux ensembles de changements :

- Protections de synchronisation : import avant checkpoint, UID/UIDVALIDITY, erreurs partielles, comparaison du port et de TLS, absence de secrets bruts dans les logs.
- Caches OAuth séparés par utilisateur et compte, permissions privées, rejet des liens symboliques et verrou de compte.
- Scan personnel, liste des jobs personnels, création/modification/activation des connecteurs et tests de connexion personnels.
- Réanalyse atomique des archives, amélioration de l'extraction des intitulés, conservation des corrections manuelles.
- Backoffice limité aux administrateurs actifs, contrôle CSRF et interdiction de se désactiver soi-même.
- Démonstration Alice/Bob et anciens jobs sans propriétaire conservés mais jamais exécutés.

Le registre des routes et l'écran des travaux combinent les fonctions des deux branches ; aucune ancienne fonction globale n'a été réactivée. Les attentes contradictoires des anciens tests ont été alignées sur les routes personnelles désormais disponibles. Les deux définitions concurrentes des mêmes tests STARTTLS ont été dédupliquées.

Un conflit sémantique, pourtant fusionné automatiquement par Git, conservait le refus 503 de la réanalyse. Les tests ont détecté cette incohérence ; la route utilise maintenant le job personnel sécurisé.

Les scripts de migration sont regroupés dans le paquet `migrate/`. Les imports de production, de démonstration et des tests utilisent ce paquet ; lancer les outils depuis la racine avec `.venv/bin/python -m migrate.<nom_du_script> --help`. Le déplacement ne lance aucune migration de données.

## Tests automatiques

- Ruff format et lint : conformes.
- Pyright : 0 erreur, 0 avertissement.
- Syntaxe JavaScript de `static/imap-form.js` : conforme.
- `python -m unittest discover -s tests -v` : **233 tests réussis**.
- `git diff --check` : conforme.

Les tests utilisent uniquement les bases temporaires, mocks et faux serveurs IMAP. Le contrôle réel ci-dessous est indépendant de cette suite.

## Démonstration Alice/Bob

Une nouvelle démonstration a été initialisée dans un répertoire temporaire ; le dossier `.demo-campus` existant n'a pas été réinitialisé.

Les tests vérifient les données, imports, checkpoints, jobs historiques ignorés et isolation des deux apprenants. Ils couvrent aussi la création d'un connecteur fictif et son test sans écriture dans le keyring réel, ainsi que la détection sans DNS.

Un contrôle HTTP loopback complémentaire a réellement lancé `demo.py serve`, connecté Alice puis Bob avec des mots de passe fictifs non affichés, et vérifié pour chacun :

- tableau accessible et absence des candidatures de l'autre ;
- pages connecteurs et jobs accessibles ;
- bandeau de démonstration hors ligne.

Le serveur temporaire a été arrêté et le répertoire temporaire supprimé. La démo remplace explicitement l'authentification, l'écriture des secrets et la détection DNS par des simulations ; ces remplacements ne sont actifs que dans son contexte. Elle interdit aussi les envois UDP en plus des connexions sortantes.

## Contrôle réel du compte personnel

Ce contrôle a été réalisé après accord explicite pour la copie des caches OAuth, puis pour un seul scan réel. Il ne s'agit pas d'une simulation.

1. Vérification du compte utilisateur n°1 actif, des quatre comptes IMAP activés et de l'absence de jobs en cours/en attente.
2. Acquisition du verrou exclusif du worker et sauvegarde SQLite cohérente, dans un répertoire privé avec fichier 0600.
3. Vérification des identités OAuth Gmail et Microsoft à partir de leurs anciens caches privés par compte.
4. Copie vers les nouveaux chemins par utilisateur, sans écrasement de destination, fichiers 0600 et répertoires 0700. Les contenus des caches sources ont été comparés avant/après et sont restés inchangés. Aucun jeton n'a été affiché.
5. Chargement d'une session locale de contrôle pour l'utilisateur n°1 par le `user_loader` normal, puis appel réel de `POST /scan` avec un jeton CSRF issu du formulaire. Cette vérification utilise le client Flask et ne prétend pas avoir testé la saisie du mot de passe personnel dans un navigateur.
6. Exécution d'un seul job par le worker personnel, sans lancer de boucle traitant d'autres jobs.

**Job :** `6383471f346b4a74ae37b94338ca7adb` — **succeeded**.

| Résultat | Valeur |
| --- | ---: |
| Réponse de `POST /scan` | 303 |
| Comptes analysés | 4 |
| Comptes ignorés | 0 |
| Checkpoints enregistrés | 4 |
| Emails de candidature détectés/ajoutés | 0 / 0 |
| Emails conservés avant/après | 144 / 144 |

Les quatre fournisseurs OVH, SFR, Gmail et Microsoft ont été analysés avec les contrôles normaux. Les emails déjà présents ont été comparés avant/après ; ils sont inchangés. Les anciens jobs sans propriétaire et les corrections manuelles sont également inchangés. Le cache personnel créé peut être renouvelé par le fonctionnement OAuth normal, tandis que les fichiers sources historiques ont été conservés intacts.

Sauvegarde créée :

```text
backups/integration-20261102T152946889418Z/before-real-scan.sqlite3
```

Ce contrôle confirme le fonctionnement aux conditions et autorisations présentes lors de son exécution ; une expiration ou révocation OAuth ultérieure reste possible.

## Utilisation de la branche intégrée

Redémarrer les processus habituels depuis cette branche :

```bash
.venv/bin/python web.py
```

Dans un autre terminal :

```bash
.venv/bin/python worker.py
```

Le processus Web déjà lancé n'a pas été interrompu automatiquement pendant l'intégration. Le contrôle réel ponctuel a libéré son verrou et n'a laissé aucun worker de vérification actif.

Pour la démonstration existante, sans la réinitialiser :

```bash
.venv/bin/python demo.py serve
```

Ne pas lancer le worker habituel pour la démo : elle possède son worker fictif interne. Les exports et l'autorisation OAuth interactive depuis le Web restent hors périmètre.

Aucun push ni déploiement n'a été effectué.
