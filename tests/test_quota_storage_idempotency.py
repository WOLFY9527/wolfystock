# -*- coding: utf-8 -*-
"""Storage-level quota idempotency foundation tests."""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.services.quota_policy_service import QuotaPolicyService
from src.storage import DatabaseManager, QuotaReservation, QuotaUsageWindow


def _fresh_db() -> DatabaseManager:
    DatabaseManager.reset_instance()
    return DatabaseManager(db_url="sqlite:///:memory:")


class QuotaStorageIdempotencyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _fresh_db()
        self.service = QuotaPolicyService(db=self.db, enforcement_enabled=True)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()

    def test_null_equivalent_quota_window_identity_is_unique(self) -> None:
        window_start = datetime(2026, 6, 10)
        window_end = window_start + timedelta(days=1)
        identity = DatabaseManager.quota_window_identity_values(
            owner_user_id=None,
            route_family="analysis",
            provider=None,
            model_tier=None,
        )

        with self.assertRaises(IntegrityError):
            with self.db.session_scope() as session:
                session.add(
                    QuotaUsageWindow(
                        owner_user_id=None,
                        route_family="analysis",
                        provider=None,
                        model_tier=None,
                        window_type="daily",
                        window_start=window_start,
                        window_end=window_end,
                        **identity,
                    )
                )
                session.flush()
                session.add(
                    QuotaUsageWindow(
                        owner_user_id="",
                        route_family="analysis",
                        provider="",
                        model_tier="",
                        window_type="daily",
                        window_start=window_start,
                        window_end=window_end,
                        **identity,
                    )
                )
                session.flush()

    def _reserve(self, *, estimated_units: int = 10):
        result = self.service.reserve_quota(
            owner_user_id="user-1",
            route_family="analysis",
            estimated_units=estimated_units,
        )
        self.assertTrue(result.allowed)
        self.assertTrue(result.reservation_id)
        return result

    def _assert_window_counts(
        self,
        reservation_id: str,
        *,
        reserved_units: int,
        consumed_units: int,
    ) -> None:
        with self.db.session_scope() as session:
            reservation = session.query(QuotaReservation).filter_by(reservation_id=reservation_id).one()
            rows = session.query(QuotaUsageWindow).filter_by(route_family=reservation.route_family).all()
            counts = {
                (int(row.reserved_units or 0), int(row.consumed_units or 0))
                for row in rows
            }

        self.assertEqual(len(rows), 4)
        self.assertEqual(counts, {(reserved_units, consumed_units)})

    def test_storage_cas_transition_reserved_to_consumed_moves_window_units_once(self) -> None:
        reservation = self._reserve(estimated_units=10)

        transition = self.db.transition_quota_reservation_terminal_cas(
            reservation_id=reservation.reservation_id,
            terminal_status="consumed",
            consumed_units=7,
            now=datetime.now(),
        )

        self.assertTrue(transition["transitioned"])
        self.assertEqual(transition["status"], "consumed")
        self.assertEqual(transition["reservation"]["status"], "consumed")
        self._assert_window_counts(reservation.reservation_id, reserved_units=0, consumed_units=7)

    def test_storage_cas_transition_reserved_to_released_reclaims_capacity(self) -> None:
        reservation = self._reserve(estimated_units=10)

        transition = self.db.transition_quota_reservation_terminal_cas(
            reservation_id=reservation.reservation_id,
            terminal_status="released",
            now=datetime.now(),
        )

        self.assertTrue(transition["transitioned"])
        self.assertEqual(transition["status"], "released")
        self.assertEqual(transition["reservation"]["status"], "released")
        self._assert_window_counts(reservation.reservation_id, reserved_units=0, consumed_units=0)

    def test_storage_cas_transition_reserved_to_expired_reclaims_capacity(self) -> None:
        reservation = self._reserve(estimated_units=10)

        transition = self.db.transition_quota_reservation_terminal_cas(
            reservation_id=reservation.reservation_id,
            terminal_status="expired",
            now=datetime.now(),
        )

        self.assertTrue(transition["transitioned"])
        self.assertEqual(transition["status"], "expired")
        self.assertEqual(transition["reservation"]["status"], "expired")
        self.assertEqual(transition["reservation"]["reason_code"], "reservation_expired")
        self._assert_window_counts(reservation.reservation_id, reserved_units=0, consumed_units=0)

    def test_storage_cas_repeated_terminal_call_returns_existing_state(self) -> None:
        reservation = self._reserve(estimated_units=10)

        first = self.db.transition_quota_reservation_terminal_cas(
            reservation_id=reservation.reservation_id,
            terminal_status="consumed",
            consumed_units=7,
            now=datetime.now(),
        )
        second = self.db.transition_quota_reservation_terminal_cas(
            reservation_id=reservation.reservation_id,
            terminal_status="consumed",
            consumed_units=9,
            now=datetime.now(),
        )

        self.assertTrue(first["transitioned"])
        self.assertFalse(second["transitioned"])
        self.assertEqual(second["status"], "consumed")
        self._assert_window_counts(reservation.reservation_id, reserved_units=0, consumed_units=7)

    def test_storage_cas_release_loser_after_consume_does_not_move_counters(self) -> None:
        reservation = self._reserve(estimated_units=10)

        consumed = self.db.transition_quota_reservation_terminal_cas(
            reservation_id=reservation.reservation_id,
            terminal_status="consumed",
            consumed_units=8,
            now=datetime.now(),
        )
        released = self.db.transition_quota_reservation_terminal_cas(
            reservation_id=reservation.reservation_id,
            terminal_status="released",
            now=datetime.now(),
        )

        self.assertTrue(consumed["transitioned"])
        self.assertFalse(released["transitioned"])
        self.assertEqual(released["status"], "consumed")
        self._assert_window_counts(reservation.reservation_id, reserved_units=0, consumed_units=8)

    def test_storage_cas_consume_loser_after_expire_does_not_move_counters(self) -> None:
        reservation = self._reserve(estimated_units=10)

        expired = self.db.transition_quota_reservation_terminal_cas(
            reservation_id=reservation.reservation_id,
            terminal_status="expired",
            now=datetime.now(),
        )
        consumed = self.db.transition_quota_reservation_terminal_cas(
            reservation_id=reservation.reservation_id,
            terminal_status="consumed",
            consumed_units=8,
            now=datetime.now(),
        )

        self.assertTrue(expired["transitioned"])
        self.assertFalse(consumed["transitioned"])
        self.assertEqual(consumed["status"], "expired")
        self.assertEqual(consumed["reservation"]["reason_code"], "reservation_expired")
        self._assert_window_counts(reservation.reservation_id, reserved_units=0, consumed_units=0)


if __name__ == "__main__":
    unittest.main()
