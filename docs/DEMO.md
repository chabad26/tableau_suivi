# Démonstration hors ligne pour le jury

## Préparer une fois

Depuis la racine du dépôt, après installation :

```bash
.venv/bin/python demo.py init
```

Saisir deux mots de passe **fictifs** de 12 caractères minimum pour Alice et Bob. Ne pas utiliser un mot de passe réel. Ils ne sont pas affichés, ni écrits en clair dans un fichier. La base ne conserve que leurs hashes.

L'initialisation crée `.demo-campus/campus.sqlite3` et un marqueur de démonstration. Si ce dossier existe déjà, la commande refuse de l'écraser. Pour une nouvelle répétition, choisir un autre dossier neuf :

```bash
.venv/bin/python demo.py init --directory .demo-campus-repetition
.venv/bin/python demo.py serve --directory .demo-campus-repetition
```

Les fichiers SQLite sont ignorés par Git ; ne pas versionner les dossiers personnels de répétition.

## Lancer

```bash
.venv/bin/python demo.py serve
```

Ouvrir **http://127.0.0.1:5001**. Le bandeau indique « Démonstration hors ligne ». Ce processus fournit aussi le worker fictif ; ne pas démarrer le worker habituel pour ce scénario. Arrêt avec Ctrl+C.

La clé de session est recréée à chaque lancement : se reconnecter après un redémarrage. L'initialisation et le serveur sur un dossier sans marqueur sont refusés. Les connexions sortantes du processus sont interdites ; aucun véritable compte IMAP, keyring ou cache OAuth n'est utilisé.

## Scénario (5 à 8 minutes)

1. Se connecter avec `alice@campus.invalid` et le mot de passe choisi.
2. Montrer les entreprises fictives : Atelier des Alpes, Campus Numérique, Studio Horizon et Tech Montagne. Les libellés portent le prénom du propriétaire. Montrer les statuts envoyée, entretien, refus et acceptée. L'acceptation est ici une donnée manuelle de démonstration, pas une détection automatique ajoutée au classificateur.
3. Ouvrir la candidature créée automatiquement depuis les trois emails de recrutement fictifs. Montrer son historique : lecture MIME, classification et import utilisent le vrai pipeline applicatif avec un serveur IMAP en mémoire.
4. Ouvrir « Mes synchronisations ». Le premier scan a déjà importé ces trois emails pendant l'initialisation. Il est terminé et possède un point de reprise.
5. Cliquer « Scanner les mails », puis actualiser les synchronisations. Le nouveau travail passe de l'attente au succès. Le serveur fictif n'ayant pas de nouveau message après UID 3, zéro email supplémentaire est attendu : cela illustre la reprise incrémentale et l'absence de doublons.
6. Utiliser un second navigateur ou se déconnecter, puis se connecter avec `bob@campus.invalid`. Bob possède ses propres entreprises, emails et travaux. Les lignes d'Alice n'apparaissent pas. Une URL de détail d'Alice renvoie 404 depuis la session de Bob.
7. Expliquer les boutons indisponibles : exports, connecteurs et réanalyse restent bloqués pendant leur migration. Ne pas présenter ces opérations comme disponibles.

## Montrer un checkpoint et les données historiques

Dans un second terminal, lecture seule de la base fictive :

```bash
.venv/bin/python - <<'PY'
import sqlite3
from pathlib import Path
path = Path('.demo-campus/campus.sqlite3').resolve()
with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as connection:
    for row in connection.execute(
        'SELECT user_id, last_uid, uid_validity FROM imap_accounts ORDER BY user_id'
    ):
        print(row)
    print(connection.execute(
        "SELECT id, user_id, state FROM jobs WHERE id = 'historique-demo'"
    ).fetchone())
PY
```

Après l'initialisation, les deux checkpoints valent UID **3**, UIDVALIDITY **777**. Le job `historique-demo` conserve un propriétaire `NULL` et l'état `queued`, même après les scans personnels : le nouveau worker ne l'exécute pas.

## Montrer les scénarios de panne sans messagerie réelle

```bash
.venv/bin/python -m unittest tests.test_sync_integration -v
```

Les tests démontrent : rollback de l'import SQLite, checkpoint inchangé après échec d'import, UID illisible puis reprise, réimport sans doublon, séparation des utilisateurs, checkpoint refusé après désactivation/réattribution/changement concurrent, erreur d'une boîte conservant les imports des autres, et absence de secrets d'exception dans les logs.

Il s'agit de simulations automatisées hors réseau. Aucun résultat de cette démonstration ne constitue une validation des connexions aux vrais fournisseurs.
