"""Oracle DROP statement generation and execution."""

from __future__ import annotations


# TPC-C tables in dependency order (children first)
TPROCC_TABLES = [
    "ORDER_LINE",
    "NEW_ORDER",
    "ORDERS",
    "HISTORY",
    "CUSTOMER",
    "STOCK",
    "ITEM",
    "DISTRICT",
    "WAREHOUSE",
]

# TPC-H tables in dependency order
TPROCH_TABLES = [
    "LINEITEM",
    "ORDERS",
    "PARTSUPP",
    "CUSTOMER",
    "SUPPLIER",
    "PART",
    "NATION",
    "REGION",
]


def get_tprocc_drop_statements(schema_user: str) -> list[str]:
    """Generate DROP TABLE statements for Oracle TPC-C tables."""
    return [
        f"DROP TABLE {schema_user}.{table} CASCADE CONSTRAINTS PURGE"
        for table in TPROCC_TABLES
    ]


def get_tproch_drop_statements(schema_user: str) -> list[str]:
    """Generate DROP TABLE statements for Oracle TPC-H tables."""
    return [
        f"DROP TABLE {schema_user}.{table} CASCADE CONSTRAINTS PURGE"
        for table in TPROCH_TABLES
    ]


def execute_drops(
    host: str,
    port: int,
    service: str,
    username: str,
    password: str,
    statements: list[str],
) -> tuple[int, list[str]]:
    """Execute DROP statements via oracledb. Returns (tables_dropped, errors)."""
    import oracledb

    errors = []
    dropped = 0

    try:
        conn = oracledb.connect(
            user=username,
            password=password,
            dsn=f"{host}:{port}/{service}",
        )
        cursor = conn.cursor()

        for stmt in statements:
            try:
                cursor.execute(stmt)
                dropped += 1
            except oracledb.DatabaseError as e:
                err_str = str(e)
                # ORA-00942: table or view does not exist - this is OK
                if "ORA-00942" in err_str:
                    dropped += 1  # Count as "handled"
                else:
                    errors.append(f"{stmt}: {err_str}")

        conn.close()
    except Exception as e:
        errors.append(f"Connection failed: {e}")

    return dropped, errors
