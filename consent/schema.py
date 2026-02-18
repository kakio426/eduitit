from functools import lru_cache

from django.db import connection
from django.db.utils import OperationalError, ProgrammingError


REQUIRED_TABLES = (
    "signatures_signaturedocument",
    "signatures_signaturerequest",
    "signatures_signatureposition",
    "signatures_signaturerecipient",
    "signatures_consentauditlog",
)


@lru_cache(maxsize=1)
def _cached_schema_status():
    try:
        existing_tables = set(connection.introspection.table_names())
    except (OperationalError, ProgrammingError) as exc:
        return False, list(REQUIRED_TABLES), str(exc)

    missing = [table for table in REQUIRED_TABLES if table not in existing_tables]
    return len(missing) == 0, missing, ""


def get_consent_schema_status(force_refresh=False):
    if force_refresh:
        _cached_schema_status.cache_clear()
    return _cached_schema_status()
