from __future__ import annotations

from llm_sca_tooling.fl.issue import normalize_issue_text


def test_github_template_sections_and_python_stack() -> None:
    issue = normalize_issue_text("""
## Expected
Validation should reject missing names.

## Actual
The request crashes.

Traceback (most recent call last):
  File "/work/repo/src/pkg/core.py", line 3, in validate
    return payload['name'].lower()
KeyError: 'name'
""")

    assert issue.expected_behaviour == "Validation should reject missing names."
    assert issue.observed_behaviour == "The request crashes."
    assert issue.stack_trace_frames[0].file_path == "src/pkg/core.py"
    assert issue.stack_trace_frames[0].line == 3
    assert issue.stack_trace_frames[0].function_name == "validate"
    assert "python" in issue.language_hints
    assert any("KeyError" in error for error in issue.error_strings)


def test_js_and_cpp_stack_frames_are_extracted() -> None:
    issue = normalize_issue_text("""
TypeError: cannot read properties of undefined
    at renderUser (src/ui/user.ts:42:13)
#0 0x000000 in Service::load (src/native/service.cpp:88)
""")

    assert [frame.file_path for frame in issue.stack_trace_frames] == [
        "src/ui/user.ts",
        "src/native/service.cpp",
    ]
    assert {"typescript", "javascript", "cpp"} & set(issue.language_hints)
    assert "renderUser" in issue.mentioned_symbols
