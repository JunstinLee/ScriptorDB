"""SQL identifier quoting helpers — dialect-aware."""

def get_quote_char(dialect_name: str) -> tuple[str, str]:
    """
    Return (open_quote, close_quote) for the given SQL dialect.

    - MySQL: uses backticks ``
    - SQLite, PostgreSQL: uses double quotes ""
    """
    if dialect_name == "mysql":
        return "`", "`"
    else:
        return '"', '"'


def quote_identifier(name: str, dialect_name: str) -> str:
    """Quote a SQL identifier (table name, column name) for the given dialect."""
    open_q, close_q = get_quote_char(dialect_name)
    escaped = name.replace(open_q, open_q + open_q)
    return f"{open_q}{escaped}{close_q}"
