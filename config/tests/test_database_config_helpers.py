import os
from unittest.mock import patch

from django.test import SimpleTestCase

from config.database import apply_database_network_overrides, normalize_database_url


class NormalizeDatabaseUrlTest(SimpleTestCase):
    def test_normalize_removes_psql_prefix_and_quotes(self):
        value = "psql 'postgres://user:pass@example.com/app'"

        self.assertEqual(
            normalize_database_url(value),
            "postgresql://user:pass@example.com/app",
        )


class ApplyDatabaseNetworkOverridesTest(SimpleTestCase):
    @patch.dict(os.environ, {"DATABASE_HOSTADDR": "13.228.46.236"}, clear=False)
    def test_database_hostaddr_env_sets_libpq_hostaddr(self):
        config = {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": "example.neon.tech",
        }

        updated = apply_database_network_overrides(
            config,
            "postgresql://user:pass@example.neon.tech/app?sslmode=require",
        )

        self.assertEqual(updated["OPTIONS"]["hostaddr"], "13.228.46.236")
        self.assertEqual(updated["HOST"], "example.neon.tech")

    @patch.dict(os.environ, {"DATABASE_PREFER_IPV4": "true", "DATABASE_HOSTADDR": ""}, clear=False)
    @patch("config.database.socket.getaddrinfo")
    def test_prefer_ipv4_resolves_hostaddr_from_hostname(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = [
            (
                None,
                None,
                None,
                None,
                ("52.220.170.93", 5432),
            )
        ]
        config = {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": "example.neon.tech",
            "PORT": 5432,
        }

        updated = apply_database_network_overrides(
            config,
            "postgresql://user:pass@example.neon.tech/app?sslmode=require",
        )

        self.assertEqual(updated["OPTIONS"]["hostaddr"], "52.220.170.93")
        mock_getaddrinfo.assert_called_once_with(
            "example.neon.tech",
            5432,
            2,
            1,
        )
