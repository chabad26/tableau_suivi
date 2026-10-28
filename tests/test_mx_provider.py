import unittest
from unittest.mock import patch

from app.mail_providers import detect_provider_smart, get_mx_hosts


class MXProviderTests(unittest.TestCase):
    def test_sfr(self):
        provider = detect_provider_smart("test@sfr.fr")

        self.assertIsNotNone(provider)
        assert provider is not None
        self.assertEqual(provider.key, "sfr")

    @patch("app.mail_providers.get_mx_hosts", return_value=["mx1.mail.ovh.net"])
    def test_ovh_domain(self, mock_mx):
        provider = detect_provider_smart("contact@example.invalid")

        mock_mx.assert_called_once_with("contact@example.invalid")
        self.assertIsNotNone(provider)
        assert provider is not None
        self.assertEqual(provider.key, "ovh")


if __name__ == "__main__":
    unittest.main()
