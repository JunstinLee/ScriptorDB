from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from tools.undo_log import (
    _undo_entries,
    _undo_groups,
    add_entry,
    create_group,
    ensure_undo_tables,
    finalize_group,
    get_entries,
    list_all_groups,
    revert_to_group,
)


@pytest.fixture
def engine():
    e = create_engine("sqlite:///", poolclass=None)
    ensure_undo_tables(e)
    return e


def test_ensure_undo_tables(engine):
    with engine.connect() as conn:
        tables = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        ).fetchall()
    names = [r[0] for r in tables]
    assert "_scriptordb_undo_groups" in names
    assert "_scriptordb_undo_entries" in names


def test_create_and_finalize_group(engine):
    with engine.connect() as conn:
        gid = create_group(conn, "s1", "r1", "test prompt")
        assert gid > 0

        row = conn.execute(
            _undo_groups.select().where(_undo_groups.c.id == gid)
        ).fetchone()
        assert row.session_id == "s1"
        assert row.run_id == "r1"
        assert row.status == "pending"
        assert row.sequence == 1

        finalize_group(conn, gid)
        row = conn.execute(
            _undo_groups.select().where(_undo_groups.c.id == gid)
        ).fetchone()
        assert row.status == "completed"
        conn.commit()


def test_add_entry(engine):
    with engine.connect() as conn:
        gid = create_group(conn, "s2", "r2", "prompt")
        add_entry(
            conn, gid, 1, "INSERT", "users",
            'DELETE FROM "users" WHERE "id" = :undo_id',
            {"undo_id": 5},
        )
        entries = get_entries(conn, gid)
        assert len(entries) == 1
        assert entries[0]["operation"] == "INSERT"
        assert entries[0]["table_name"] == "users"
        conn.commit()


def test_list_all_groups(engine):
    with engine.connect() as conn:
        create_group(conn, "s3", "r3", "p1")
        create_group(conn, "s4", "r4", "p2")
        conn.commit()

    groups = list_all_groups(engine)
    assert len(groups) >= 2


def test_revert_to_group(engine):
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS t1 (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(text("INSERT INTO t1 (id, name) VALUES (1, 'old')"))
        conn.commit()

        g1 = create_group(conn, "s5", "r5", "insert alice")
        add_entry(
            conn, g1, 1, "INSERT", "t1",
            'DELETE FROM "t1" WHERE "id" = :undo_id',
            {"undo_id": 2},
        )
        conn.execute(text("INSERT INTO t1 (id, name) VALUES (2, 'alice')"))
        finalize_group(conn, g1)

        g2 = create_group(conn, "s5", "r6", "update name")
        add_entry(
            conn, g2, 1, "UPDATE", "t1",
            'UPDATE "t1" SET "name" = :undo_name WHERE "id" = :undo_pk_id',
            {"undo_name": "alice", "undo_pk_id": 2},
        )
        conn.execute(text("UPDATE t1 SET name = 'bob' WHERE id = 2"))
        finalize_group(conn, g2)
        conn.commit()

    reverted = revert_to_group(engine, g1)
    assert g2 in reverted

    with engine.connect() as conn:
        row = conn.execute(text("SELECT name FROM t1 WHERE id = 2")).fetchone()
        assert row is None or row[0] == "alice"


def test_revert_to_group_respects_sequence(engine):
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS t2 (id INTEGER PRIMARY KEY, val TEXT)"))
        conn.commit()

        g1 = create_group(conn, "s6", "r7", "insert first")
        add_entry(
            conn, g1, 1, "INSERT", "t2",
            'DELETE FROM "t2" WHERE "id" = :undo_id',
            {"undo_id": 1},
        )
        conn.execute(text("INSERT INTO t2 (id, val) VALUES (1, 'first')"))
        finalize_group(conn, g1)

        g2 = create_group(conn, "s6", "r8", "insert second")
        add_entry(
            conn, g2, 1, "INSERT", "t2",
            'DELETE FROM "t2" WHERE "id" = :undo_id',
            {"undo_id": 2},
        )
        conn.execute(text("INSERT INTO t2 (id, val) VALUES (2, 'second')"))
        finalize_group(conn, g2)
        conn.commit()

    revert_to_group(engine, g1)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id FROM t2")).fetchall()
        ids = [r[0] for r in rows]
        assert 2 not in ids


def test_sequence_auto_increment(engine):
    with engine.connect() as conn:
        g1 = create_group(conn, "s7", "r9", "first")
        g2 = create_group(conn, "s7", "r10", "second")

        r1 = conn.execute(
            _undo_groups.select().where(_undo_groups.c.id == g1)
        ).fetchone()
        r2 = conn.execute(
            _undo_groups.select().where(_undo_groups.c.id == g2)
        ).fetchone()
        assert r2.sequence == r1.sequence + 1
        conn.commit()
