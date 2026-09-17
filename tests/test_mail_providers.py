import unittest

from app.mail_providers import (
    detect_provider,
    extract_domain,
    get_provider,
)


class MailProviderTests(
    unittest.TestCase
):
    def test_extract_domain(self):
        self.assertEqual(
            extract_domain(
                "Olivier@SFR.FR"
            ),
            "sfr.fr",
        )

    def test_detect_sfr(self):
        provider = detect_provider(
            "test@neuf.fr"
        )

        self.assertIsNotNone(provider)

        assert provider is not None

        self.assertEqual(
            provider.key,
            "sfr",
        )

    def test_detect_orange(self):
        provider = detect_provider(
            "test@wanadoo.fr"
        )

        self.assertIsNotNone(provider)

        assert provider is not None

        self.assertEqual(
            provider.key,
            "orange",
        )

    def test_unknown_domain(self):
        provider = detect_provider(
            "test@sabledoux.fr"
        )

        self.assertIsNone(provider)

    def test_get_provider(self):
        provider = get_provider(
            "ovh"
        )

        self.assertIsNotNone(provider)

        assert provider is not None

        self.assertEqual(
            provider.name,
            "OVHcloud",
        )


if __name__ == "__main__":
    unittest.main()