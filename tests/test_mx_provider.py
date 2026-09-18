import unittest

from app.mail_providers import (
    detect_provider_smart,
    get_mx_hosts,
)


class MXProviderTests(unittest.TestCase):
    def test_sfr(self):
        provider = detect_provider_smart(
            "test@sfr.fr"
        )

        self.assertIsNotNone(provider)

        assert provider is not None

        self.assertEqual(
            provider.key,
            "sfr",
        )

    def test_ovh_domain(self):
        address = "contact@olidev.ovh"

        print()
        print("MX :", get_mx_hosts(address))

        provider = detect_provider_smart(
            address
        )

        print(
            "Fournisseur :",
            provider.name
            if provider
            else "Inconnu",
        )

        self.assertIsNotNone(provider)

        assert provider is not None

        self.assertEqual(
            provider.key,
            "ovh",
        )


if __name__ == "__main__":
    unittest.main()