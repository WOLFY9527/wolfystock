# -*- coding: utf-8 -*-
from __future__ import annotations

import scripts.clean_test_history as clean


class _FakeQuery:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def filter(self, *_args, **_kwargs) -> _FakeQuery:
        return self

    def order_by(self, *_args, **_kwargs) -> _FakeQuery:
        return self

    def all(self) -> list[object]:
        return list(self._rows)


class _FakeSession:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows
        self.deleted: list[object] = []
        self.commit_calls = 0
        self.rollback_calls = 0

    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def query(self, _model) -> _FakeQuery:
        return _FakeQuery(self.rows)

    def delete(self, row: object) -> None:
        self.deleted.append(row)

    def commit(self) -> None:
        self.commit_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1


class _FakeDatabase:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    def get_session(self) -> _FakeSession:
        return self._session


def test_clean_test_history_records_defaults_to_dry_run_without_delete_or_commit(monkeypatch) -> None:
    rows = [object(), object()]
    session = _FakeSession(rows)
    monkeypatch.setattr(clean.DatabaseManager, "get_instance", lambda: _FakeDatabase(session))

    deleted = clean.clean_test_history_records()

    assert deleted == 2
    assert session.deleted == []
    assert session.commit_calls == 0
    assert session.rollback_calls == 1


def test_clean_test_history_records_execute_deletes_and_commits(monkeypatch) -> None:
    rows = [object(), object(), object()]
    session = _FakeSession(rows)
    monkeypatch.setattr(clean.DatabaseManager, "get_instance", lambda: _FakeDatabase(session))

    deleted = clean.clean_test_history_records(dry_run=False)

    assert deleted == 3
    assert session.deleted == rows
    assert session.commit_calls == 1
    assert session.rollback_calls == 0


def test_main_defaults_to_dry_run_and_prints_execute_guidance(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    def _fake_clean_test_history_records(**kwargs) -> int:
        captured.update(kwargs)
        return 2

    monkeypatch.setattr(clean, "clean_test_history_records", _fake_clean_test_history_records)

    exit_code = clean.main([])

    assert exit_code == 0
    assert captured["dry_run"] is True
    output = capsys.readouterr().out
    assert "would_delete=2" in output
    assert "--execute" in output


def test_main_execute_prints_warning_and_deletes(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    def _fake_clean_test_history_records(**kwargs) -> int:
        captured.update(kwargs)
        return 2

    monkeypatch.setattr(clean, "clean_test_history_records", _fake_clean_test_history_records)

    exit_code = clean.main(["--execute"])

    assert exit_code == 0
    assert captured["dry_run"] is False
    output = capsys.readouterr().out
    assert "WARNING" in output
    assert "deleted=2" in output
