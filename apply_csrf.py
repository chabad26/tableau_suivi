"""Applique une protection CSRF Flask-WTF au dépôt Job Tracker.

Lancer à la racine du dépôt : python path/to/apply_csrf.py
Le script est idempotent et refuse les structures inattendues.
"""

import re
from pathlib import Path

root = Path.cwd()
required = [
    root / "app/web/__init__.py",
    root / "tests/helpers.py",
    root / "requirements.txt",
]
if not all(p.is_file() for p in required):
    raise SystemExit("Erreur : lancer le script depuis la racine de tableau_suivi.")

changes = {}


def replace(path, before, after):
    contents = changes.get(path, path.read_text(encoding="utf-8"))
    if after in contents:
        return
    if before not in contents:
        raise SystemExit(
            f"Structure inattendue dans {path}. Aucune modification écrite."
        )
    changes[path] = contents.replace(before, after, 1)


req = root / "requirements.txt"
s = req.read_text(encoding="utf-8")
if not any(line.lower().startswith("flask-wtf") for line in s.splitlines()):
    changes[req] = s.rstrip() + "\nFlask-WTF>=1.2,<2\n"

factory = root / "app/web/__init__.py"
replace(
    factory,
    "from flask import Flask\n",
    "from flask import Flask\nfrom flask_wtf.csrf import CSRFProtect\n",
)
replace(
    factory,
    "    register_blueprints(app)\n",
    "    CSRFProtect(app)\n\n    register_blueprints(app)\n",
)

helpers = root / "tests/helpers.py"
replace(
    helpers,
    "self.app.config.update(TESTING=True)",
    "self.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)",
)

forms = [
    "templates/index.html",
    "templates/application.html",
    "templates/new_application.html",
    "templates/connectors.html",
    "templates/imap_add.html",
    "templates/imap_edit.html",
]
count = 0
for rel in forms:
    path = root / rel
    s = path.read_text(encoding="utf-8")
    # Inserts CSRF only into POST forms, never GET search forms.
    pattern = r"(<form\b[^>]*\bmethod\s*=\s*[\"\']post[\"\'][^>]*>)"

    def insert(match):
        global count
        count += 1
        tail = s[match.end() :]
        if re.match(
            r"\s*<input\s+type=[\"\']hidden[\"\']\s+name=[\"\']csrf_token[\"\']", tail
        ):
            return match.group(0)
        return (
            match.group(0)
            + '\n            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">'
        )

    changes[path] = re.sub(pattern, insert, s, flags=re.I | re.S)

# Le template présent sur GitHub comporte un ancien nom de route.
imap = root / "templates/imap_add.html"
s = changes[imap]
s = s.replace("url_for('save_imap_account')", "url_for('connectors.save_imap_account')")
changes[imap] = s

# Only write once every expected transform has been verified.
if count < 8:
    raise SystemExit(
        f"Seulement {count} formulaires POST détectés, vérifie les templates (aucun fichier écrit)."
    )

for path, value in changes.items():
    if path.read_text(encoding="utf-8") != value:
        path.write_text(value, encoding="utf-8")
        print("Modifié :", path.relative_to(root))
print("Terminé. Formulaires POST analysés :", count)
