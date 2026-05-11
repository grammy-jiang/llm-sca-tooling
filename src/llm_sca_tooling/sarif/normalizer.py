"""Normalize SARIF rules, severities, and alerts."""

from __future__ import annotations

import re
from collections.abc import Iterable

from llm_sca_tooling.sarif.fingerprint import (
    compute_alert_fingerprint,
    compute_partial_fingerprint,
)
from llm_sca_tooling.sarif.models import (
    AlertLocation,
    NormalizedAlert,
    NormalizedRule,
    NormalizedSarifRun,
    NormalizedSeverity,
    SarifLocation,
    SarifLog,
    SarifReportingDescriptor,
    SarifResult,
    SarifRun,
)

__all__ = [
    "extract_cwe_ids",
    "normalize_rule_family",
    "normalize_sarif_log",
    "normalize_severity",
    "predicate_id",
]

_SEVERITY_ORDER = {
    NormalizedSeverity.informational: 0,
    NormalizedSeverity.low: 1,
    NormalizedSeverity.medium: 2,
    NormalizedSeverity.high: 3,
    NormalizedSeverity.critical: 4,
}

_CWE_FAMILY = {
    "CWE-22": "path-traversal",
    "CWE-78": "command-injection",
    "CWE-79": "xss",
    "CWE-89": "sql-injection",
    "CWE-94": "command-injection",
    "CWE-120": "buffer-overflow",
    "CWE-190": "integer-overflow",
    "CWE-327": "crypto-weak",
    "CWE-330": "insecure-random",
    "CWE-502": "deserialization",
    "CWE-611": "xxe",
    "CWE-798": "hardcoded-secret",
}


def normalize_sarif_log(
    log: SarifLog,
    *,
    repo_id: str,
    snapshot_id: str,
    git_sha: str,
    run_id: str,
    analyser_id: str | None = None,
    ruleset_id: str = "default",
    raw_sarif_artifact_ref: str | None = None,
) -> NormalizedSarifRun:
    first_run = log.runs[0] if log.runs else _empty_run()
    analyser = analyser_id or first_run.tool.driver.name.lower()
    rules = _normalize_rules(first_run, analyser)
    rules_by_id = {rule.rule_id: rule for rule in rules}
    alerts = [
        _normalize_alert(result, rules_by_id, analyser, run_id)
        for result in first_run.results
    ]
    return NormalizedSarifRun(
        run_id=run_id,
        repo_id=repo_id,
        snapshot_id=snapshot_id,
        git_sha=git_sha,
        analyser_id=analyser,
        analyser_version=first_run.tool.driver.version,
        analyser_name=first_run.tool.driver.name,
        ruleset_id=ruleset_id,
        invocation_exit_code=first_run.invocation_exit_code,
        invocation_successful=first_run.invocation_successful,
        rules=rules,
        alerts=alerts,
        raw_sarif_artifact_ref=raw_sarif_artifact_ref,
    )


def normalize_severity(
    analyser_id: str,
    raw_level: str | None,
    properties: dict[str, object] | None = None,
) -> NormalizedSeverity:
    props = properties or {}
    security_severity = props.get("security-severity") or props.get("security_severity")
    if security_severity is not None:
        try:
            score = float(str(security_severity))
        except ValueError:
            score = -1.0
        if score >= 9.0:
            return NormalizedSeverity.critical
        if score >= 7.0:
            return NormalizedSeverity.high
    tool = analyser_id.lower()
    level = (raw_level or "warning").lower()
    if tool == "bandit":
        severity = str(
            props.get("issue_severity") or props.get("severity") or level
        ).upper()
        confidence = str(
            props.get("issue_confidence") or props.get("confidence") or ""
        ).upper()
        if severity == "HIGH" and confidence == "HIGH":
            return NormalizedSeverity.high
        if severity in {"HIGH", "MEDIUM"}:
            return NormalizedSeverity.medium
        return NormalizedSeverity.low
    if tool == "sonarqube":
        return {
            "blocker": NormalizedSeverity.critical,
            "critical": NormalizedSeverity.high,
            "major": NormalizedSeverity.medium,
            "minor": NormalizedSeverity.low,
            "info": NormalizedSeverity.informational,
        }.get(level, NormalizedSeverity.medium)
    if level in {"error", "high"}:
        return NormalizedSeverity.high
    if level in {"warning", "medium", "recommendation"}:
        return NormalizedSeverity.medium
    if level in {"note", "info", "low"}:
        return NormalizedSeverity.low
    return NormalizedSeverity.informational


def extract_cwe_ids(*values: object) -> list[str]:
    found: set[str] = set()
    for value in values:
        items = value if isinstance(value, list) else [value]
        for item in items:
            text = str(item)
            for match in re.findall(r"(?:CWE[-:]?\s*)?(\d{1,5})", text, flags=re.I):
                found.add(f"CWE-{int(match)}")
    return sorted(found, key=lambda item: int(item.split("-", 1)[1]))


def normalize_rule_family(
    rule_id: str, cwe_ids: Iterable[str], tags: Iterable[str]
) -> str:
    for cwe in cwe_ids:
        if cwe in _CWE_FAMILY:
            return _CWE_FAMILY[cwe]
    haystack = " ".join([rule_id, *tags]).lower()
    patterns = {
        "sql-injection": ["sqli", "sql-injection", "sql_injection", "cwe-89"],
        "xss": ["xss", "cross-site"],
        "path-traversal": ["path-traversal", "directory traversal"],
        "command-injection": ["command-injection", "shell"],
        "hardcoded-secret": ["hardcoded", "secret", "b105", "password"],
        "crypto-weak": ["weak-crypto", "crypto"],
        "null-deref": ["null", "nullptr"],
    }
    for family, needles in patterns.items():
        if any(needle in haystack for needle in needles):
            return family
    return "other"


def predicate_id(analyser_id: str, rule_id: str, properties: dict[str, object]) -> str:
    if analyser_id == "bandit":
        return f"BANDIT-{rule_id}"
    github_alert = properties.get("github/alertNumber")
    if github_alert is not None:
        return f"GHAS-{github_alert}"
    return rule_id


def _normalize_rules(run: SarifRun, analyser_id: str) -> list[NormalizedRule]:
    rules: list[NormalizedRule] = []
    for raw_rule in run.tool.driver.rules:
        rules.append(_normalize_rule(raw_rule, analyser_id))
    seen = {rule.rule_id for rule in rules}
    for result in run.results:
        if result.rule_id and result.rule_id not in seen:
            rules.append(
                _normalize_rule(
                    SarifReportingDescriptor(
                        id=result.rule_id, properties=result.properties
                    ),
                    analyser_id,
                    raw_level=result.level,
                )
            )
            seen.add(result.rule_id)
    return rules


def _normalize_rule(
    rule: SarifReportingDescriptor, analyser_id: str, raw_level: str | None = None
) -> NormalizedRule:
    tags = _tags(rule.properties)
    cwes = extract_cwe_ids(
        rule.properties.get("cwe"),
        rule.properties.get("cwe-id"),
        rule.properties.get("cwe-ids"),
        tags,
    )
    severity = normalize_severity(
        analyser_id, raw_level or rule.default_level, rule.properties
    )
    family = normalize_rule_family(rule.id, cwes, tags)
    return NormalizedRule(
        rule_id=rule.id,
        analyser_id=analyser_id,
        name=rule.name,
        short_description=rule.short_description,
        full_description=rule.full_description,
        help_uri=rule.help_uri,
        raw_severity=raw_level or rule.default_level,
        normalized_severity=severity,
        cwe_ids=cwes,
        rule_family=family,
        predicate_id=predicate_id(analyser_id, rule.id, rule.properties),
        tags=tags,
        confidence_level="parser" if _SEVERITY_ORDER[severity] >= 3 else "heuristic",
    )


def _normalize_alert(
    result: SarifResult,
    rules: dict[str, NormalizedRule],
    analyser_id: str,
    run_id: str,
) -> NormalizedAlert:
    rule_id = result.rule_id or "unknown"
    rule = rules.get(rule_id)
    location = result.locations[0] if result.locations else SarifLocation()
    alert_location = _alert_location(location)
    severity = normalize_severity(analyser_id, result.level, result.properties)
    if rule and _SEVERITY_ORDER[rule.normalized_severity] > _SEVERITY_ORDER[severity]:
        severity = rule.normalized_severity
    family = rule.rule_family if rule else "other"
    fingerprint = compute_alert_fingerprint(
        analyser_id=analyser_id,
        rule_id=rule_id,
        file_path=alert_location.file_path,
        start_line=alert_location.start_line,
        message=result.message,
        snippet=_snippet(location),
    )
    partial = compute_partial_fingerprint(
        rule_family=family,
        normalized_severity=severity.value,
        start_column=alert_location.start_column,
    )
    suppression = result.suppressions[0] if result.suppressions else {}
    return NormalizedAlert(
        alert_id=f"{analyser_id}:{fingerprint}",
        run_id=run_id,
        rule_id=rule_id,
        analyser_id=analyser_id,
        raw_level=result.level,
        normalized_severity=severity,
        message=result.message,
        file_path=alert_location.file_path,
        start_line=alert_location.start_line,
        start_column=alert_location.start_column,
        end_line=alert_location.end_line,
        end_column=alert_location.end_column,
        related_locations=[_alert_location(loc) for loc in result.related_locations],
        suppressed=bool(result.suppressions),
        suppression_kind=(
            str(suppression.get("kind"))
            if suppression.get("kind") is not None
            else None
        ),
        suppression_status=(
            str(suppression.get("status"))
            if suppression.get("status") is not None
            else None
        ),
        suppression_justification=(
            str(suppression.get("justification"))
            if suppression.get("justification") is not None
            else None
        ),
        fingerprint=fingerprint,
        partial_fingerprint=partial,
        raw_fingerprints={**result.fingerprints, **result.partial_fingerprints},
        baseline_state=result.baseline_state,
        properties={**result.properties, "rule_family": family},
    )


def _alert_location(location: SarifLocation) -> AlertLocation:
    physical = location.physical_location
    artifact = physical.artifact_location if physical else None
    region = physical.region if physical else None
    return AlertLocation(
        file_path=artifact.resolved_path if artifact else None,
        start_line=region.start_line if region else None,
        start_column=region.start_column if region else None,
        end_line=region.end_line if region else None,
        end_column=region.end_column if region else None,
        message=location.message,
    )


def _snippet(location: SarifLocation) -> str | None:
    physical = location.physical_location
    if physical and physical.region:
        return physical.region.snippet_text
    return None


def _tags(properties: dict[str, object]) -> list[str]:
    raw_tags = properties.get("tags") or properties.get("problem.severity")
    if isinstance(raw_tags, list):
        return [str(tag) for tag in raw_tags]
    if isinstance(raw_tags, str):
        return [raw_tags]
    return []


def _empty_run() -> SarifRun:
    from llm_sca_tooling.sarif.models import SarifTool, SarifToolComponent

    return SarifRun(tool=SarifTool(driver=SarifToolComponent(name="external")))
