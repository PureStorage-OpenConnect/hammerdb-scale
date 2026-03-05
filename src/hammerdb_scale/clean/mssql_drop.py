"""MSSQL DROP statement generation and execution."""

from __future__ import annotations


# TPC-C tables in dependency order
TPROCC_TABLES = [
    "order_line",
    "new_order",
    "orders",
    "history",
    "customer",
    "stock",
    "item",
    "district",
    "warehouse",
]

# TPC-H tables in dependency order
TPROCH_TABLES = [
    "lineitem",
    "orders",
    "partsupp",
    "customer",
    "supplier",
    "part",
    "nation",
    "region",
]


def get_tprocc_drop_statements(database_name: str) -> list[str]:
    """Generate DROP TABLE statements for MSSQL TPC-C tables."""
    stmts = [f"USE {database_name}"]
    stmts.extend(f"DROP TABLE IF EXISTS dbo.{table}" for table in TPROCC_TABLES)
    return stmts


def get_tproch_drop_statements(database_name: str) -> list[str]:
    """Generate DROP TABLE statements for MSSQL TPC-H tables."""
    stmts = [f"USE {database_name}"]
    stmts.extend(f"DROP TABLE IF EXISTS dbo.{table}" for table in TPROCH_TABLES)
    return stmts


def execute_drops(
    host: str,
    port: int,
    username: str,
    password: str,
    statements: list[str],
) -> tuple[int, list[str]]:
    """Connect via pymssql and execute DROP statements.

    Returns (tables_dropped, errors).
    """
    import pymssql

    errors = []
    dropped = 0

    try:
        conn = pymssql.connect(
            server=host,
            port=port,
            user=username,
            password=password,
            login_timeout=10,
        )
        cursor = conn.cursor()

        for stmt in statements:
            try:
                cursor.execute(stmt)
                conn.commit()
                if stmt.startswith("DROP"):
                    dropped += 1
            except pymssql.DatabaseError as e:
                errors.append(f"{stmt}: {e}")

        conn.close()
    except Exception as e:
        errors.append(f"Connection failed: {e}")

    return dropped, errors
