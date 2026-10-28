Installation dans le projet tableau_suivi

1. Copier .github/workflows/python-ci.yml à la racine du dépôt, en conservant les dossiers.
2. Remplacer tests/test_mx_provider.py par la version jointe, qui simule la réponse DNS.
3. Ajouter la ligne suivante à requirements.txt :
   dnspython
4. Pour reproduire les contrôles localement :
   .venv/bin/python -m pip install -r requirements-dev.txt
   .venv/bin/ruff check .
   .venv/bin/ruff format --check .
   .venv/bin/python -m compileall -q app tests web.py worker.py
   npx --yes pyright
   .venv/bin/python -m unittest discover -s tests -v
5. Commit et push. Consulter l'onglet Actions sur GitHub.

IMPORTANT : le workflow ne lance pas web.py ni worker.py, ne scanne aucune véritable boîte mail et ne demande pas de secrets OAuth. Les tests doivent rester hors ligne.
