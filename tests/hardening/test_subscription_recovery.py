"""Tests for SubscriptionRecoveryManager."""

from __future__ import annotations

from llm_sca_tooling.hardening.subscription_recovery import SubscriptionRecoveryManager


def test_subscribe_and_recover_returns_resource_key() -> None:
    mgr = SubscriptionRecoveryManager()
    mgr.subscribe("client1", "resource://repo/abc")
    state = mgr.recover("client1")
    assert "resource://repo/abc" in state


def test_recover_unknown_client_returns_empty_dict() -> None:
    mgr = SubscriptionRecoveryManager()
    state = mgr.recover("unknown")
    assert state == {}


def test_unsubscribe_removes_resource() -> None:
    mgr = SubscriptionRecoveryManager()
    mgr.subscribe("client1", "resource://repo/abc")
    mgr.unsubscribe("client1", "resource://repo/abc")
    state = mgr.recover("client1")
    assert "resource://repo/abc" not in state


def test_record_notification_stores_record() -> None:
    mgr = SubscriptionRecoveryManager()
    mgr.subscribe("client1", "resource://repo/abc")
    mgr.record_notification("resource://repo/abc", {"ts": "2025-01-01T00:00:00Z"})
    # No error expected


def test_acknowledge_updates_last_received() -> None:
    mgr = SubscriptionRecoveryManager()
    mgr.subscribe("client1", "resource://repo/abc")
    ts = "2025-01-01T00:00:00+00:00"
    mgr.acknowledge("client1", "resource://repo/abc", ts)
    # Should not raise


def test_multiple_clients_independent() -> None:
    mgr = SubscriptionRecoveryManager()
    mgr.subscribe("c1", "resource://r1")
    mgr.subscribe("c2", "resource://r2")
    assert "resource://r1" in mgr.recover("c1")
    assert "resource://r2" not in mgr.recover("c1")
