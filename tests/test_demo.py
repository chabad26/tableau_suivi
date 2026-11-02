"""Vérification de la démonstration dans des processus et répertoires isolés."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


class DemoTests(unittest.TestCase):
    def test_initialization_scan_isolation_and_network_guard(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            production = root / "production.sqlite3"
            production.write_bytes(b"PRODUCTION-SENTINEL")
            script = r"""
import json
import secrets
import socket
import sqlite3
import sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
import demo
root = Path(sys.argv[1]) / 'demo'
root.mkdir(mode=0o700)
(root / 'campus.sqlite3').touch(mode=0o600)
demo.configure_demo(root)
with ExitStack() as stack:
    demo.offline_transport(stack)
    password = secrets.token_urlsafe(24)
    demo.seed_demo(password, password)
    from app.database import get_connection
    from app.owned_jobs import enqueue_user_job, get_user_job, run_next_user_job
    from app.owned_applications import get_user_applications
    from app.web import create_app
    from werkzeug.security import check_password_hash
    with get_connection() as connection:
        users = connection.execute('SELECT * FROM users ORDER BY id').fetchall()
        assert len(users) == 2
        assert check_password_hash(users[0]['password_hash'], password)
        assert connection.execute('SELECT COUNT(*) FROM emails').fetchone()[0] == 6
        assert connection.execute('SELECT COUNT(*) FROM imap_accounts WHERE last_uid=3 AND uid_validity=777').fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM applications WHERE current_status='ACCEPTED'").fetchone()[0] == 2
    alice, bob = [row['id'] for row in users]
    assert len(get_user_applications(alice)) == 5
    assert len(get_user_applications(bob)) == 5
    app = create_app()
    app.config.update(TESTING=True)
    client = app.test_client()
    import re
    token = re.search(r'name="csrf_token"\s+value="([^"]+)"', client.get('/login').text).group(1)
    assert client.post('/login', data={'email':'alice@campus.invalid', 'password':password, 'csrf_token':token}).status_code == 303
    page = client.get('/')
    assert 'Atelier des Alpes — Alice' in page.text
    assert 'Atelier des Alpes — Bob' not in page.text
    job_id = enqueue_user_job(alice, 'scan')
    assert run_next_user_job()
    assert json.loads(get_user_job(alice, job_id)['result'])['added'] == 0
    with get_connection() as connection:
        assert connection.execute("SELECT state FROM jobs WHERE id='historique-demo'").fetchone()[0] == 'queued'
    try:
        with socket.socket() as connection:
            connection.connect(('127.0.0.1', 9))
    except RuntimeError:
        pass
    else:
        raise AssertionError('Le réseau sortant doit être bloqué')
    assert not (root / 'oauth').exists()
    assert (root / 'campus.sqlite3').stat().st_mode & 0o777 == 0o600
"""
            result = subprocess.run(
                [sys.executable, "-c", script, str(root)],
                cwd=PROJECT,
                env={**os.environ, "DATABASE_PATH": str(production)},
                text=True,
                capture_output=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(production.read_bytes(), b"PRODUCTION-SENTINEL")

    def test_initialization_refuses_existing_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            sentinel = Path(temporary) / "existing.txt"
            sentinel.write_text("conserver")
            result = subprocess.run(
                [sys.executable, "demo.py", "init", "--directory", temporary],
                cwd=PROJECT,
                text=True,
                capture_output=True,
                timeout=10,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("aucune donnée ne sera écrasée", result.stderr)
            self.assertEqual(sentinel.read_text(), "conserver")
            self.assertFalse((Path(temporary) / "campus.sqlite3").exists())

    def test_server_refuses_unmarked_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = subprocess.run(
                [sys.executable, "demo.py", "serve", "--directory", temporary],
                cwd=PROJECT,
                text=True,
                capture_output=True,
                timeout=10,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((Path(temporary) / "campus.sqlite3").exists())
