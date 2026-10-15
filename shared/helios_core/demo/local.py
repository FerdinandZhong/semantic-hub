"""Bounded in-memory SQL over an immutable, explicitly typed serving snapshot."""

from __future__ import annotations

import csv
import io
import threading
from datetime import date

import sqlglot
from sqlglot import exp

from helios_core.engines.base import Engine, QueryResult
from .registry import DemoError, PackSnapshot


class LocalPackEngine(Engine):
    name = "local_duckdb"
    sqlglot_dialect = "duckdb"

    def __init__(self, pack: PackSnapshot):
        import duckdb

        self._lock = threading.Lock()
        self._tables = {t.name for t in pack.tables}
        self._con = duckdb.connect(
            config={"threads": "1", "memory_limit": "256MB", "enable_external_access": "false"}
        )
        try:
            self._con.execute("SET TimeZone = 'UTC'")
            # Values remain strings until DuckDB casts into these declared types.
            # No CSV sniffing, filesystem table functions, or source credentials.
            for table in pack.tables:
                definitions = ", ".join(f'"{name}" {datatype}' for name, datatype in table.columns)
                self._con.execute(f'CREATE TABLE "{table.name}" ({definitions})')
                reader = csv.reader(io.StringIO(table.csv_bytes.decode("utf-8")))
                next(reader)
                placeholders = ",".join("?" for _ in table.columns)
                rows = [tuple(None if v == "" else v for v in row) for row in reader]
                if rows:
                    self._con.executemany(
                        f'INSERT INTO "{table.name}" VALUES ({placeholders})', rows
                    )
            self._con.execute("SET lock_configuration = true")
        except Exception:
            self._con.close()
            raise

    def query(self, sql: str, limit: int | None = 1000, *, timeout: float = 5.0) -> QueryResult:
        if type(limit) is not int or not 1 <= limit <= 1000 or not 0 < timeout <= 30:
            raise DemoError("Invalid local execution budget")
        statements = sqlglot.parse(sql, read="duckdb")
        if len(statements) != 1 or not isinstance(statements[0], exp.Select):
            raise DemoError("Only one bounded SELECT is permitted")
        tree = statements[0]
        if (
            tree.args.get("with_")
            or tree.args.get("into")
            or tree.args.get("locks")
            or len(list(tree.find_all(exp.Select))) != 1
        ):
            raise DemoError("Nested queries are outside the local demo contract")
        allowed_functions = {
            "SUM",
            "AVG",
            "MIN",
            "MAX",
            "COUNT",
            "CASE",
            "IF",
            "COALESCE",
            "AND",
            "OR",
        }
        for node in tree.walk():
            if isinstance(node, exp.Table):
                if (
                    not isinstance(node.this, exp.Identifier)
                    or node.name not in self._tables
                    or node.db
                    or node.catalog
                ):
                    raise DemoError("Query references an undeclared source")
            if isinstance(node, exp.Cast):
                # The typed compiler emits DATE literals as CASTs. Permit only that
                # exact shape, not arbitrary casts or new executable functions.
                if (isinstance(node.this, exp.Literal) and node.this.is_string
                        and node.args['to'].this == exp.DataType.Type.DATE):
                    try:
                        date.fromisoformat(node.this.this)
                    except ValueError:
                        raise DemoError('Invalid date literal') from None
                    continue
            if isinstance(node, exp.Func) and node.sql_name() not in allowed_functions:
                raise DemoError("Query function is outside the local demo contract")
        if not list(tree.find_all(exp.Table)):
            raise DemoError("Query must use the selected pack")
        bounded = tree.limit(limit).sql(dialect="duckdb")
        with self._lock:
            timer = threading.Timer(timeout, self._con.interrupt)
            timer.daemon = True
            timer.start()
            try:
                cursor = self._con.execute(bounded)
                return QueryResult([c[0] for c in cursor.description], cursor.fetchmany(limit))
            finally:
                timer.cancel()
                timer.join()

    def ping(self) -> bool:
        with self._lock:
            return self._con.execute("SELECT 1").fetchone() == (1,)

    def close(self) -> None:
        with self._lock:
            self._con.close()
