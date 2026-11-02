# Validation de la branche Campus

Contrôle local du 2 novembre 2026, Linux, Python 3.14.4, Ruff 0.16.7. Branche `feature/demo-campus-finalisation` ; base de comparaison : `main` local au démarrage du travail.

## Résultats

| Contrôle | Résultat |
| --- | --- |
| `.venv/bin/ruff format .` | Aucun fichier restant à reformater au contrôle final |
| `.venv/bin/ruff format --check .` | Conforme |
| `.venv/bin/ruff check .` | All checks passed |
| `npx --yes pyright` | 0 errors, 0 warnings, 0 informations |
| `.venv/bin/python -m unittest discover -s tests -v` | 155 tests, OK |
| `git diff --check` | Aucune erreur |

Point de départ vérifié : 126 tests, OK, Ruff et Pyright conformes. La progression inclut la remise en collection de tests auparavant définis hors des classes unittest ; l'augmentation du total ne correspond donc pas uniquement à de nouveaux scénarios.

## Scénarios d'intégration

`tests/test_sync_integration.py` utilise le vrai scanner MIME/classification, l'importateur et de vraies transactions SQLite temporaires. Seuls le transport IMAP et la récupération du mot de passe sont fictifs. Les connexions réseau sont interdites par la fixture.

- Scan → détection → import → checkpoint, avec Alice et Bob séparés.
- Erreur SQLite au deuxième message : rollback du premier et aucun checkpoint avancé.
- UID illisible : succès partiel signalé, checkpoint avant l'erreur, reprise sans doublon.
- Réimport complet sans doublon.
- Compte désactivé, réattribué, port/TLS ou curseur modifié : checkpoint refusé.
- Une boîte indisponible conserve les messages importés des autres boîtes.
- UIDVALIDITY absent : import conservé sans checkpoint ; changement de génération : rescan sans doublon.
- Exception fictive contenant une valeur sensible : aucune fuite dans les logs UID.

D'autres tests couvrent le CSRF, le propriétaire issu de session, la liste personnelle des jobs, les caches OAuth, les anciens jobs conservés, STARTTLS et l'arrêt du worker.

## Démonstration vérifiée

`tests/test_demo.py` exécute l'initialisation dans un processus séparé avec une base sentinelle externe. Il vérifie la conservation de cette sentinelle, les deux utilisateurs, les six emails importés, les deux checkpoints, les statuts fictifs, l'isolation de l'interface et le refus d'une connexion sortante. Il vérifie aussi le parcours serveur avec le lancement HTTP remplacé par un stub : port, debug désactivé, cookie distinct et bandeau de démonstration.

Un contrôle complémentaire a lancé réellement `demo.py init` puis `demo.py serve` dans un répertoire temporaire, avec des mots de passe fictifs aléatoires non affichés. La page `/login` a répondu HTTP 200 sur loopback avec le bandeau attendu, puis le serveur s'est arrêté proprement sur SIGINT. Aucun navigateur ni connexion à un vrai fournisseur n'a été utilisé. La répétition visuelle devant le jury reste à effectuer selon `DEMO.md`.

## Données préservées et limites

Aucune migration de la base réelle, aucune synchronisation réelle, aucune lecture/écriture de véritable jeton OAuth. Le premier contrôle complet utilisait un chemin SQLite temporaire imposé au processus ; le test IMAP qui initialisait auparavant le chemin habituel a ensuite été corrigé pour utiliser sa propre fixture temporaire.

Les anciens jobs restent conservés et ne sont pas exécutés par le nouveau worker. Les routes globales non migrées demeurent en 503. Les détails des risques résiduels et de la compatibilité OAuth figurent dans `SECURITE.md`.

## Fichiers créés ou modifiés

- [.gitignore](../.gitignore)
- [README.md](../README.md)
- [app/connectors/imap.py](../app/connectors/imap.py)
- [app/jobs.py](../app/jobs.py)
- [app/oauth_store.py](../app/oauth_store.py)
- [app/offline_imap.py](../app/offline_imap.py)
- [app/owned_imap.py](../app/owned_imap.py)
- [app/owned_jobs.py](../app/owned_jobs.py)
- [app/owned_scanner.py](../app/owned_scanner.py)
- [app/statuses.py](../app/statuses.py)
- [app/web/__init__.py](../app/web/__init__.py)
- [app/web/jobs.py](../app/web/jobs.py)
- [demo.py](../demo.py)
- [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)
- [docs/DEMO.md](../docs/DEMO.md)
- [docs/PULL_REQUEST.md](../docs/PULL_REQUEST.md)
- [docs/SECURITE.md](../docs/SECURITE.md)
- [docs/VALIDATION.md](../docs/VALIDATION.md)
- [templates/base.html](../templates/base.html)
- [templates/index.html](../templates/index.html)
- [templates/jobs.html](../templates/jobs.html)
- [tests/test_app_factory.py](../tests/test_app_factory.py)
- [tests/test_auth.py](../tests/test_auth.py)
- [tests/test_csrf.py](../tests/test_csrf.py)
- [tests/test_demo.py](../tests/test_demo.py)
- [tests/test_extractor.py](../tests/test_extractor.py)
- [tests/test_imap_connector.py](../tests/test_imap_connector.py)
- [tests/test_jobs.py](../tests/test_jobs.py)
- [tests/test_oauth_store.py](../tests/test_oauth_store.py)
- [tests/test_owned_jobs.py](../tests/test_owned_jobs.py)
- [tests/test_owned_scanner.py](../tests/test_owned_scanner.py)
- [tests/test_personal_dashboard.py](../tests/test_personal_dashboard.py)
- [tests/test_settings.py](../tests/test_settings.py)
- [tests/test_sync_integration.py](../tests/test_sync_integration.py)
- [tests/test_sync_routes.py](../tests/test_sync_routes.py)
- [tests/test_web.py](../tests/test_web.py)
- [tests/test_worker.py](../tests/test_worker.py)
- [web.py](../web.py)
- [worker.py](../worker.py)
