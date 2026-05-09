from __future__ import annotations

import pytest

from llm_sca_tooling.plugins.backlog import DbusStub, GrpcStub, MqttStub, ProtobufStub, ZeroMQStub
from llm_sca_tooling.plugins.capability import InterfaceKind
from llm_sca_tooling.plugins.http_rest import HttpRestPlugin
from llm_sca_tooling.plugins.registry import PluginRegistry


def test_plugin_registry_reports_capabilities_and_availability() -> None:
    registry = PluginRegistry([HttpRestPlugin(), GrpcStub()])
    assert registry.get("http-rest") is not None
    assert [plugin.plugin_id for plugin in registry.available_plugins()] == ["http-rest"]
    assert registry.capability_report()[0].interface_kinds == [InterfaceKind.HTTP]
    with pytest.raises(Exception):
        registry.register(HttpRestPlugin())
    registry.unregister("grpc")
    assert registry.get("grpc") is None


def test_backlog_stubs_are_registered_unavailable() -> None:
    for plugin in [GrpcStub(), ProtobufStub(), ZeroMQStub(), MqttStub(), DbusStub()]:
        assert plugin.check_availability().available is False
        assert plugin.describe_capability().interface_kinds
        with pytest.raises(NotImplementedError):
            plugin.traverse("node:x", "both", None)  # type: ignore[arg-type]
