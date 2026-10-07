from unittest.mock import patch


def test_settings_paths_and_dates(self):
    import os

    from app import settings

    with patch.dict(os.environ, {"GMAIL_TOKEN_FILE": "tokens/fixture.json"}):
        self.assertEqual(
            settings.configured_path("GMAIL_TOKEN_FILE", ""),
            settings.PROJECT_ROOT / "tokens/fixture.json",
        )
    configured = settings.configured_date(
        "2026-08-01T00:00:00+00:00"
    )

    offset = configured.utcoffset()

    assert offset is not None

    self.assertEqual(
        offset.total_seconds(),
        0,
    )
    self.assertIsNotNone(settings.configured_date("2026-08-01").tzinfo)
    with self.assertRaises(ValueError):
        settings.configured_date("incorrect")

def test_dotenv_loaded_outside_project_and_environment_wins(self):
    import os
    import subprocess
    import sys
    from pathlib import Path

    from app import settings

    module_dir = self.root / "app"
    module_dir.mkdir()
    config = module_dir / "settings.py"
    config.write_text(Path(settings.__file__).read_text())
    (self.root / ".env").write_text(
        "MICROSOFT_CLIENT_ID=fixture-file\nGMAIL_TOKEN_FILE=tokens/fixture.json\nSCAN_START_DATE=2026-07-01\n"
    )
    script = "import runpy, sys; s=runpy.run_path(sys.argv[1]); print(s['MICROSOFT_CLIENT_ID']); print(s['GMAIL_TOKEN_FILE']); print(s['API_START_DATE'].isoformat())"
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"MICROSOFT_CLIENT_ID", "GMAIL_TOKEN_FILE", "SCAN_START_DATE"}
    }
    result = subprocess.check_output(
        [sys.executable, "-c", script, str(config)],
        cwd="/tmp",
        env=environment,
        text=True,
    )
    self.assertIn("fixture-file", result)
    self.assertIn(str(self.root / "tokens/fixture.json"), result)
    self.assertIn("2026-07-01T00:00:00+02:00", result)
    environment["MICROSOFT_CLIENT_ID"] = "fixture-process"
    result = subprocess.check_output(
        [sys.executable, "-c", script, str(config)],
        cwd="/tmp",
        env=environment,
        text=True,
    )
    self.assertIn("fixture-process", result)
