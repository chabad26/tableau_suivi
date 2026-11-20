# Intégration Campus : résultat vérifié

Compte rendu historique du contrôle du 2 novembre 2026 sur la branche `integration/campus-finalisation`, intégrant les connecteurs Campus. Les résultats ci-dessous correspondent à cette date.

## Résolution des conflits

La fusion conserve les deux ensembles de changements :

- Protections de synchronisation : import avant checkpoint, UID/UIDVALIDITY, erreurs partielles, comparaison du port et de TLS, absence de secrets bruts dans les logs.
- Caches OAuth séparés par utilisateur et compte, permissions privées, rejet des liens symboliques et verrou de compte.
- Scan personnel, liste des jobs personnels, création/modification/activation des connecteurs et tests de connexion personnels.
- Réanalyse atomique des archives, amélioration de l'extraction des intitulés, conservation des corrections manuelles.
- Backoffice limité aux administrateurs actifs, contrôle CSRF et interdiction de se désactiver soi-même.
- Anciens jobs sans propriétaire conservés mais jamais exécutés.

Le registre des routes et l'écran des travaux combinent les fonctions des deux branches ; aucune ancienne fonction globale n'a été réactivée. Les attentes contradictoires des anciens tests ont été alignées sur les routes personnelles désormais disponibles. Les deux définitions concurrentes des mêmes tests STARTTLS ont été dédupliquées.

Un conflit sémantique, pourtant fusionné automatiquement par Git, conservait le refus 503 de la réanalyse. Les tests ont détecté cette incohérence ; la route utilise maintenant le job personnel sécurisé.

Les scripts de migration sont regroupés dans le paquet `migrate/`. Les imports de production et des tests utilisent ce paquet ; lancer les outils depuis la racine avec `.venv/bin/python -m migrate.<nom_du_script> --help`. Le déplacement ne lance aucune migration de données.

## Tests automatiques

- Ruff format et lint : conformes.
- Pyright : 0 erreur, 0 avertissement.
- Syntaxe JavaScript de `static/imap-form.js` : conforme.
- `python -m unittest discover -s tests -v` : **233 tests réussis**.
- `git diff --check` : conforme.

Les tests utilisent uniquement les bases temporaires, mocks et faux serveurs IMAP. Le contrôle réel ci-dessous est indépendant de cette suite.

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

Les exports et l’autorisation OAuth interactive depuis le Web restent hors périmètre.

Aucun push ni déploiement n'a été effectué.
