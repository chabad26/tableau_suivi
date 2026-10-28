import unittest

from app.web import create_app


class AppFactoryTests(unittest.TestCase):
    def test_factory_creates_independent_apps(self):
        app1 = create_app()
        app2 = create_app()

        self.assertIsNot(app1, app2)

        app1.config["TESTING"] = True

        self.assertFalse(app2.config["TESTING"])

    def test_blueprints_are_registered(self):
        app = create_app()
        
        self.assertEqual(
            set(app.blueprints), {"applications", "connectors", "exports", "jobs"}
        )

    def test_templates_are_available(self):
        app = create_app()

        template = app.jinja_env.get_template("index.html")

        self.assertIsNotNone(template)