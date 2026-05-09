from __future__ import annotations


def test_package_imports() -> None:
    import llm_sca_tooling

    assert llm_sca_tooling.__version__ == "0.1.0"
