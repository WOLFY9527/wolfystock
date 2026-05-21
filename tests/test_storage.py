# -*- coding: utf-8 -*-
import unittest
import sys
import os
from datetime import datetime, timedelta
from types import SimpleNamespace

# Ensure src module can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.storage import DatabaseManager
from src.analyzer import AnalysisResult
from src.repositories.analysis_repo import AnalysisRepository
from src.repositories.scanner_repo import ScannerRepository
from src.storage import AppUserSession

class TestStorage(unittest.TestCase):

    def _build_analysis_result(self, *, code: str, name: str) -> AnalysisResult:
        return AnalysisResult(
            code=code,
            name=name,
            sentiment_score=70,
            trend_prediction="看多",
            operation_advice="持有",
            analysis_summary=f"{name} 分析摘要",
        )
    
    def test_parse_sniper_value(self):
        """测试解析狙击点位数值"""
        
        # 1. 正常数值
        self.assertEqual(DatabaseManager._parse_sniper_value(100), 100.0)
        self.assertEqual(DatabaseManager._parse_sniper_value(100.5), 100.5)
        self.assertEqual(DatabaseManager._parse_sniper_value("100"), 100.0)
        self.assertEqual(DatabaseManager._parse_sniper_value("100.5"), 100.5)
        
        # 2. 包含中文描述和"元"
        self.assertEqual(DatabaseManager._parse_sniper_value("建议在 100 元附近买入"), 100.0)
        self.assertEqual(DatabaseManager._parse_sniper_value("价格：100.5元"), 100.5)
        
        # 3. 包含干扰数字（修复的Bug场景）
        # 之前 "MA5" 会被错误提取为 5.0，现在应该提取 "元" 前面的 100
        text_bug = "无法给出。需等待MA5数据恢复，在股价回踩MA5且乖离率<2%时考虑100元"
        self.assertEqual(DatabaseManager._parse_sniper_value(text_bug), 100.0)
        
        # 4. 更多干扰场景
        text_complex = "MA10为20.5，建议在30元买入"
        self.assertEqual(DatabaseManager._parse_sniper_value(text_complex), 30.0)
        
        text_multiple = "支撑位10元，阻力位20元" # 应该提取最后一个"元"前面的数字，即20，或者更复杂的逻辑？
        # 当前逻辑是找最后一个冒号，然后找之后的第一个"元"，提取中间的数字。
        # 测试没有冒号的情况
        self.assertEqual(DatabaseManager._parse_sniper_value("30元"), 30.0)
        
        # 测试多个数字在"元"之前
        self.assertEqual(DatabaseManager._parse_sniper_value("MA5 10 20元"), 20.0)
        
        # 5. Fallback: no "元" character — extracts last non-MA number
        self.assertEqual(DatabaseManager._parse_sniper_value("102.10-103.00（MA5附近）"), 103.0)
        self.assertEqual(DatabaseManager._parse_sniper_value("97.62-98.50（MA10附近）"), 98.5)
        self.assertEqual(DatabaseManager._parse_sniper_value("93.40下方（MA20支撑）"), 93.4)
        self.assertEqual(DatabaseManager._parse_sniper_value("108.00-110.00（前期高点阻力）"), 110.0)

        # 6. 无效输入
        self.assertIsNone(DatabaseManager._parse_sniper_value(None))
        self.assertIsNone(DatabaseManager._parse_sniper_value(""))
        self.assertIsNone(DatabaseManager._parse_sniper_value("没有数字"))
        self.assertIsNone(DatabaseManager._parse_sniper_value("MA5但没有元"))

        # 7. 回归：括号内技术指标数字不应被提取
        self.assertNotEqual(DatabaseManager._parse_sniper_value("1.52-1.53 (回踩MA5/10附近)"), 10.0)
        self.assertNotEqual(DatabaseManager._parse_sniper_value("1.55-1.56(MA5/M20支撑)"), 20.0)
        self.assertNotEqual(DatabaseManager._parse_sniper_value("1.49-1.50(MA60附近企稳)"), 60.0)
        # 验证正确值在区间内
        self.assertIn(DatabaseManager._parse_sniper_value("1.52-1.53 (回踩MA5/10附近)"), [1.52, 1.53])
        self.assertIn(DatabaseManager._parse_sniper_value("1.55-1.56(MA5/M20支撑)"), [1.55, 1.56])
        self.assertIn(DatabaseManager._parse_sniper_value("1.49-1.50(MA60附近企稳)"), [1.49, 1.50])

    def test_get_chat_sessions_prefix_is_scoped_by_colon_boundary(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")

        db.save_conversation_message("telegram_12345:chat", "user", "first user")
        db.save_conversation_message("telegram_123456:chat", "user", "second user")

        sessions = db.get_chat_sessions(session_prefix="telegram_12345")

        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["session_id"], "telegram_12345:chat")

        DatabaseManager.reset_instance()

    def test_get_chat_sessions_can_include_legacy_exact_session_id(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")

        db.save_conversation_message("feishu_u1", "user", "legacy chat")
        db.save_conversation_message("feishu_u1:ask_600519", "user", "ask session")

        sessions = db.get_chat_sessions(
            session_prefix="feishu_u1:",
            extra_session_ids=["feishu_u1"],
        )

        self.assertEqual({item["session_id"] for item in sessions}, {"feishu_u1", "feishu_u1:ask_600519"})

        DatabaseManager.reset_instance()

    def test_list_recent_analysis_symbols_returns_shared_recent_code_name_view(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")

        db.save_analysis_history(
            result=self._build_analysis_result(code="600001", name="算力龙头"),
            query_id="query_600001",
            report_type="simple",
            news_content="",
            save_snapshot=False,
        )
        db.save_analysis_history(
            result=self._build_analysis_result(code="600002", name="机器人核心"),
            query_id="query_600002",
            report_type="simple",
            news_content="",
            save_snapshot=False,
        )

        recent_symbols = db.list_recent_analysis_symbols()
        scanner_repo = ScannerRepository(db)
        analysis_repo = AnalysisRepository(db)

        self.assertEqual(
            recent_symbols[:2],
            [("600002", "机器人核心"), ("600001", "算力龙头")],
        )
        self.assertEqual(scanner_repo.list_recent_analysis_symbols()[:2], recent_symbols[:2])
        self.assertEqual(
            analysis_repo.list_recent_named_codes()[:2],
            [
                {"code": "600002", "name": "机器人核心"},
                {"code": "600001", "name": "算力龙头"},
            ],
        )

        DatabaseManager.reset_instance()

    def test_list_recent_analysis_symbols_is_limited_deduped_and_owner_scoped(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")
        db.create_or_update_app_user(user_id="owner-a", username="owner-a")
        db.create_or_update_app_user(user_id="owner-b", username="owner-b")

        db.save_analysis_history(
            result=self._build_analysis_result(code="600001", name="旧名称"),
            query_id="query_owner_a_old",
            report_type="simple",
            news_content="",
            save_snapshot=False,
            owner_id="owner-a",
        )
        db.save_analysis_history(
            result=self._build_analysis_result(code="600003", name="其他用户"),
            query_id="query_owner_b",
            report_type="simple",
            news_content="",
            save_snapshot=False,
            owner_id="owner-b",
        )
        db.save_analysis_history(
            result=self._build_analysis_result(code="600002", name="机器人核心"),
            query_id="query_owner_a_second",
            report_type="simple",
            news_content="",
            save_snapshot=False,
            owner_id="owner-a",
        )
        db.save_analysis_history(
            result=self._build_analysis_result(code="600001", name="新名称"),
            query_id="query_owner_a_new",
            report_type="simple",
            news_content="",
            save_snapshot=False,
            owner_id="owner-a",
        )

        recent_symbols = db.list_recent_analysis_symbols(owner_id="owner-a", limit=2)
        scanner_repo = ScannerRepository(db)
        analysis_repo = AnalysisRepository(db, owner_id="owner-a")

        self.assertEqual(recent_symbols, [("600001", "新名称"), ("600002", "机器人核心")])
        self.assertEqual(
            scanner_repo.list_recent_analysis_symbols(owner_id="owner-a", limit=1),
            [("600001", "新名称")],
        )
        self.assertEqual(
            analysis_repo.list_recent_named_codes(limit=2),
            [
                {"code": "600001", "name": "新名称"},
                {"code": "600002", "name": "机器人核心"},
            ],
        )
        self.assertEqual(len(db.list_recent_analysis_symbols(limit=2)), 2)

        DatabaseManager.reset_instance()

    def test_touch_and_revoke_app_user_session_keep_session_state_consistent(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")

        user = db.ensure_bootstrap_admin_user()
        expires_at = datetime.now() + timedelta(hours=1)
        created = db.create_app_user_session(
            session_id="session-1",
            user_id=str(user.id),
            expires_at=expires_at,
        )

        self.assertEqual(created.session_id, "session-1")
        self.assertTrue(db.touch_app_user_session("session-1"))
        self.assertTrue(db.revoke_app_user_session("session-1"))

        row = db.get_app_user_session("session-1")
        self.assertIsNotNone(row)
        self.assertIsNotNone(row.last_seen_at)
        self.assertIsNotNone(row.revoked_at)

        DatabaseManager.reset_instance()

    def test_revoke_all_app_user_sessions_counts_distinct_phase_a_and_legacy_sessions(self):
        class _FakePhaseAStore:
            def __init__(self) -> None:
                self._user = SimpleNamespace(id="user-1")
                self.revoked_user_ids = []

            def get_app_user(self, user_id: str):
                if user_id == "user-1":
                    return self._user
                return None

            def list_active_app_user_session_ids(self, user_id: str) -> list[str]:
                if user_id == "user-1":
                    return ["phase-a-session"]
                return []

            def get_app_user_session(self, session_id: str):
                return None

            def revoke_all_app_user_sessions(self, user_id: str) -> int:
                self.revoked_user_ids.append(user_id)
                return 1

        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")
        db.create_or_update_app_user(
            user_id="user-1",
            username="user-1",
            display_name="User 1",
            role="user",
            password_hash=None,
            is_active=True,
        )
        db.create_app_user_session(
            session_id="legacy-session",
            user_id="user-1",
            expires_at=datetime.now() + timedelta(hours=1),
        )

        db._phase_a_enabled = True
        db._phase_a_store = _FakePhaseAStore()

        revoked = db.revoke_all_app_user_sessions("user-1")

        self.assertEqual(revoked, 2)
        self.assertEqual(db._phase_a_store.revoked_user_ids, ["user-1"])
        with db.get_session() as session:
            legacy_row = (
                session.query(AppUserSession)
                .filter(AppUserSession.session_id == "legacy-session")
                .first()
            )
        self.assertIsNotNone(legacy_row)
        self.assertIsNotNone(legacy_row.revoked_at)

        DatabaseManager.reset_instance()

if __name__ == '__main__':
    unittest.main()
