from __future__ import annotations

import pytest
from sqlalchemy import text

from tools.undo import UndoRepository


@pytest.fixture
def repo(tmp_path):
    r = UndoRepository(f"sqlite:///{tmp_path / 'undo.db'}", "")
    r.ensure_tables()
    return r


def test_ensure_undo_tables(repo):
    with repo.db.session() as conn:
        tables = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        ).fetchall()
    names = [r[0] for r in tables]
    assert "_scriptordb_undo_groups" in names
    assert "_scriptordb_undo_entries" in names


def test_create_and_finalize_group(repo):
    gid = repo.create_group("s1", "r1", "test prompt")
    assert gid > 0

    with repo.db.session() as conn:
        row = conn.execute(
            text(
                "SELECT session_id, run_id, status, sequence "
                "FROM _scriptordb_undo_groups WHERE id = :gid"
            ),
            {"gid": gid},
        ).fetchone()
    assert row[0] == "s1"
    assert row[1] == "r1"
    assert row[2] == "pending"
    assert row[3] == 1

    repo.finalize_group(gid)
    with repo.db.session() as conn:
        row = conn.execute(
            text(
                "SELECT status FROM _scriptordb_undo_groups WHERE id = :gid"
            ),
            {"gid": gid},
        ).fetchone()
    assert row[0] == "completed"


def test_add_entry(repo):
    gid = repo.create_group("s2", "r2", "prompt")
    repo.add_entry(
        gid, 1, "INSERT", "users",
        'DELETE FROM "users" WHERE "id" = :undo_id',
        {"undo_id": 5},
    )
    entries = repo.get_entries(gid)
    assert len(entries) == 1
    assert entries[0]["operation"] == "INSERT"
    assert entries[0]["table_name"] == "users"


def test_list_all_groups(repo):
    repo.create_group("s3", "r3", "p1")
    repo.create_group("s4", "r4", "p2")

    groups = repo.list_all_groups()
    assert len(groups) >= 2


def test_revert_to_group(repo):
    with repo.db.session() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS t1 (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(text("INSERT INTO t1 (id, name) VALUES (1, 'old')"))

    g1 = repo.create_group("s5", "r5", "insert alice")
    repo.add_entry(
        g1, 1, "INSERT", "t1",
        'DELETE FROM "t1" WHERE "id" = :undo_id',
        {"undo_id": 2},
    )
    with repo.db.session() as conn:
        conn.execute(text("INSERT INTO t1 (id, name) VALUES (2, 'alice')"))
    repo.finalize_group(g1)

    g2 = repo.create_group("s5", "r6", "update name")
    repo.add_entry(
        g2, 1, "UPDATE", "t1",
        'UPDATE "t1" SET "name" = :undo_name WHERE "id" = :undo_pk_id',
        {"undo_name": "alice", "undo_pk_id": 2},
    )
    with repo.db.session() as conn:
        conn.execute(text("UPDATE t1 SET name = 'bob' WHERE id = 2"))
    repo.finalize_group(g2)

    reverted = repo.revert_to_group(g1)
    assert g2 in reverted

    with repo.db.session() as conn:
        row = conn.execute(text("SELECT name FROM t1 WHERE id = 2")).fetchone()
    assert row is None or row[0] == "alice"


def test_revert_to_group_respects_sequence(repo):
    with repo.db.session() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS t2 (id INTEGER PRIMARY KEY, val TEXT)"))

    g1 = repo.create_group("s6", "r7", "insert first")
    repo.add_entry(
        g1, 1, "INSERT", "t2",
        'DELETE FROM "t2" WHERE "id" = :undo_id',
        {"undo_id": 1},
    )
    with repo.db.session() as conn:
        conn.execute(text("INSERT INTO t2 (id, val) VALUES (1, 'first')"))
    repo.finalize_group(g1)

    g2 = repo.create_group("s6", "r8", "insert second")
    repo.add_entry(
        g2, 1, "INSERT", "t2",
        'DELETE FROM "t2" WHERE "id" = :undo_id',
        {"undo_id": 2},
    )
    with repo.db.session() as conn:
        conn.execute(text("INSERT INTO t2 (id, val) VALUES (2, 'second')"))
    repo.finalize_group(g2)

    repo.revert_to_group(g1)
    with repo.db.session() as conn:
        rows = conn.execute(text("SELECT id FROM t2")).fetchall()
    ids = [r[0] for r in rows]
    assert 2 not in ids


def test_sequence_auto_increment(repo):
    g1 = repo.create_group("s7", "r9", "first")
    g2 = repo.create_group("s7", "r10", "second")

    with repo.db.session() as conn:
        r1 = conn.execute(
            text("SELECT sequence FROM _scriptordb_undo_groups WHERE id = :gid"),
            {"gid": g1},
        ).fetchone()
        r2 = conn.execute(
            text("SELECT sequence FROM _scriptordb_undo_groups WHERE id = :gid"),
            {"gid": g2},
        ).fetchone()
    assert r2[0] == r1[0] + 1
