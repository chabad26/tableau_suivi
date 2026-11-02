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
    from flask import Flask
    def fake_run(app, **kwargs):
        assert kwargs['port'] == 5001
        assert not kwargs['debug']
        assert app.config['DEMO_MODE']
        assert app.config['SESSION_COOKIE_NAME'] == 'job_tracker_demo_session'
        assert 'Démonstration hors ligne' in app.test_client().get('/login').text
    with patch.object(Flask, 'run', new=fake_run):
        demo.serve_demo(root)
    # Les nouvelles routes doivent rester totalement fictives dans la démo.
    page = client.get('/connectors/imap/add')
    assert page.status_code == 200
    token = re.search(r'name="csrf_token"\s+value="([^"]+)"', page.text).group(1)
    with patch('keyring.set_password', side_effect=AssertionError('Keyring réel interdit')) as keyring:
        response = client.post('/connectors/imap/add', data={
            'csrf_token': token, 'email': 'alice-extra@campus.invalid',
            'provider': 'imap', 'host': 'imap.demo.invalid', 'port': '993',
            'use_ssl': 'on', 'username': 'alice-extra@campus.invalid',
            'folder': 'INBOX', 'auth_method': 'password', 'password': secrets.token_urlsafe(24),
        })
        assert response.status_code == 303
        keyring.assert_not_called()
    with get_connection() as connection:
        extra = connection.execute("SELECT id FROM imap_accounts WHERE email='alice-extra@campus.invalid' AND user_id=?", (alice,)).fetchone()[0]
    assert client.post(f'/connectors/imap/{extra}/test', data={'csrf_token':token}).status_code == 303
    assert run_next_user_job()
    with get_connection() as connection:
        assert connection.execute("SELECT state FROM jobs WHERE user_id=? AND kind=?", (alice,f'test:imap:{extra}')).fetchone()[0] == 'succeeded'
        assert connection.execute('SELECT last_uid FROM imap_accounts WHERE id=?', (extra,)).fetchone()[0] == 0
    with patch('app.mail_providers.get_mx_hosts', side_effect=AssertionError('DNS réel interdit')) as dns:
        assert client.post('/connectors/imap/detect', data={'email':'user@example.com','csrf_token':token}).status_code == 200
        dns.assert_not_called()
    bob_client = app.test_client()
    bob_token = re.search(r'name="csrf_token"\s+value="([^"]+)"', bob_client.get('/login').text).group(1)
    assert bob_client.post('/login', data={'email':'bob@campus.invalid','password':password,'csrf_token':bob_token}).status_code == 303
    assert 'Atelier des Alpes — Bob' in bob_client.get('/').text
    assert 'Atelier des Alpes — Alice' not in bob_client.get('/').text
    assert 'alice-extra@campus.invalid' not in bob_client.get('/connectors').text
    assert bob_client.get(f'/connectors/imap/{extra}/edit').status_code == 404
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
