# Storage Seam Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce low-risk duplication around `DatabaseManager` analysis-history and app-user session helpers without changing runtime behavior.

**Architecture:** Keep `src/storage.py` as the authority for the underlying queries, then let repositories delegate to shared `DatabaseManager` helpers instead of repeating the same SQL. Limit this pass to behavior-preserving seams that are easy to verify with focused tests.

**Tech Stack:** Python 3, SQLAlchemy ORM, pytest, unittest

---

### Task 1: Unify recent analysis symbol reads

**Files:**
- Modify: `src/storage.py`
- Modify: `src/repositories/analysis_repo.py`
- Modify: `src/repositories/scanner_repo.py`
- Test: `tests/test_storage.py`

- [ ] **Step 1: Write the failing test**

```python
def test_list_recent_analysis_symbols_returns_latest_code_name_pairs(self):
    DatabaseManager.reset_instance()
    db = DatabaseManager(db_url="sqlite:///:memory:")
    # seed two history rows
    # call db.list_recent_analysis_symbols()
    # assert returned tuples preserve newest-first order
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_storage.py -q`
Expected: FAIL because `DatabaseManager.list_recent_analysis_symbols` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
def list_recent_analysis_symbols(self) -> list[tuple[str, str | None]]:
    with self.get_session() as session:
        rows = session.execute(
            select(AnalysisHistory.code, AnalysisHistory.name)
            .order_by(AnalysisHistory.created_at.desc())
        ).all()
    return [
        (str(code), str(name) if name is not None else None)
        for code, name in rows
        if code
    ]
```

- [ ] **Step 4: Reuse the shared helper in repositories**

```python
def list_recent_named_codes(self) -> List[Dict[str, Optional[str]]]:
    return [
        {"code": code.strip(), "name": (name.strip() or None) if isinstance(name, str) else name}
        for code, name in self.db.list_recent_analysis_symbols()
    ]
```

```python
def list_recent_analysis_symbols(self) -> List[Tuple[str, Optional[str]]]:
    return self.db.list_recent_analysis_symbols()
```

- [ ] **Step 5: Run tests to verify it passes**

Run: `python3 -m pytest tests/test_storage.py -q`
Expected: PASS

### Task 2: Unify app-user session row lookup

**Files:**
- Modify: `src/storage.py`
- Test: `tests/test_storage.py`

- [ ] **Step 1: Write the failing test**

```python
def test_revoke_app_user_session_and_touch_reuse_single_lookup_path(self):
    DatabaseManager.reset_instance()
    db = DatabaseManager(db_url="sqlite:///:memory:")
    # seed bootstrap user and session
    # touch session, then revoke session
    # assert both operations still succeed
```

- [ ] **Step 2: Run test to verify behavior is captured**

Run: `python3 -m pytest tests/test_storage.py -q`
Expected: PASS after test is added, proving the refactor has regression coverage before edits.

- [ ] **Step 3: Write minimal implementation**

```python
def _sqlite_find_app_user_session_row(self, session, *, session_id: str) -> AppUserSession | None:
    return session.execute(
        select(AppUserSession).where(AppUserSession.session_id == session_id).limit(1)
    ).scalar_one_or_none()
```

- [ ] **Step 4: Replace duplicate inline queries**

```python
row = self._sqlite_find_app_user_session_row(session, session_id=normalized_session_id)
```

Use this in:
- `_sqlite_get_app_user_session`
- `_sqlite_touch_app_user_session`
- `_sqlite_revoke_app_user_session`

- [ ] **Step 5: Run tests to verify it passes**

Run: `python3 -m pytest tests/test_storage.py tests/test_auth_api.py -q`
Expected: PASS

### Task 3: Targeted verification and audit note update

**Files:**
- Modify: the audit work report

- [ ] **Step 1: Record the completed seam reductions**

```md
- unified recent analysis symbol reads behind `DatabaseManager.list_recent_analysis_symbols()`
- unified app-user session row lookup behind a single private helper
```

- [ ] **Step 2: Run focused verification**

Run: `python3 -m pytest tests/test_storage.py tests/test_market_scanner_service.py tests/test_auth_api.py -q`
Expected: PASS

- [ ] **Step 3: Summarize the bounded outcome**

```md
Verdict: completed_with_bounded_scope
```
