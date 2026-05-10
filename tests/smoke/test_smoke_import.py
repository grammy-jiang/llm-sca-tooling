from __future__ import annotations


def test_package_imports() -> None:
    import llm_sca_tooling

    assert isinstance(llm_sca_tooling.__version__, str)
    assert llm_sca_tooling.__version__  # non-empty
