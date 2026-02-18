"""
Legacy compatibility shim.

`consent` models were moved to `consent.models`.
This module is kept because old signatures migrations import
`signatures.consent_models._generate_access_token`.
"""

import secrets

from consent.models import (  # noqa: F401
    ConsentAuditLog,
    SignatureDocument,
    SignaturePosition,
    SignatureRecipient,
    SignatureRequest,
)


def _generate_access_token():
    return secrets.token_urlsafe(24)


__all__ = [
    "_generate_access_token",
    "SignatureDocument",
    "SignatureRequest",
    "SignaturePosition",
    "SignatureRecipient",
    "ConsentAuditLog",
]
