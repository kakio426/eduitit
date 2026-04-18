import logging


logger = logging.getLogger(__name__)


def safe_storage_url(file_field, default: str = "") -> str:
    if not file_field:
        return default
    try:
        return file_field.url or default
    except Exception as exc:
        logger.warning(
            "Unable to resolve storage url for %s: %s",
            getattr(file_field, "name", "") or "<unnamed>",
            exc,
        )
        return default
