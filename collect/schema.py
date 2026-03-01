from functools import lru_cache

from django.db import connection
from django.db.utils import OperationalError, ProgrammingError


REQUIRED_TABLE_COLUMNS = {
    "collect_collectionrequest": ("bti_integration_source",),
    "collect_submission": ("integration_source", "integration_ref"),
}


@lru_cache(maxsize=1)
def _cached_schema_status():
    try:
        existing_tables = set(connection.introspection.table_names())
    except (OperationalError, ProgrammingError) as exc:
        return False, list(REQUIRED_TABLE_COLUMNS.keys()), {}, str(exc)

    missing_tables = []
    missing_columns = {}

    for table_name, required_columns in REQUIRED_TABLE_COLUMNS.items():
        if table_name not in existing_tables:
            missing_tables.append(table_name)
            continue
        with connection.cursor() as cursor:
            table_desc = connection.introspection.get_table_description(cursor, table_name)
        existing_columns = {column.name for column in table_desc}
        missing = [column for column in required_columns if column not in existing_columns]
        if missing:
            missing_columns[table_name] = missing

    is_ready = not missing_tables and not missing_columns
    return is_ready, missing_tables, missing_columns, ""


def get_collect_schema_status(force_refresh=False):
    if force_refresh:
        _cached_schema_status.cache_clear()
    return _cached_schema_status()
