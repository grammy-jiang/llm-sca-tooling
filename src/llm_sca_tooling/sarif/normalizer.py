"""Normalize SARIF producer-specific alerts into stable evidence records."""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable

from llm_sca_tooling.schemas.enums import ArtifactKind, RedactionStatus
from llm_sca_tooling.schemas.provenance import ArtifactRef
from llm_sca_tooling.sarif.fingerprint import compute_alert_fingerprint, compute_partial_fingerprint
from llm_sca_tooling.sarif.models import (
    AlertCodeFlow,
    AlertLocation,
    NormalizedAlert,
    NormalizedRule,
    NormalizedSarifRun,
    NormalizedSeverity,
    SarifCodeFlow,
    SarifLocation,
    SarifLog,
    SarifReportingDescriptor,
    SarifResult,
)
from llm_sca_tooling.storage.ids import stable_hash
from llm_sca_tooling.storage.workspace import _now_ts


CWE_FAMILIES = {
    "CWE-89": "sql-injection",
    "CWE-79": "xss",
    "CWE-22": "path-traversal",
    "CWE-78": "command-injection",
    "CWE-611": "xxe",
    "CWE-918": "ssrf",
    "CWE-502": "deserialization",
    "CWE-476": "null-deref",
    "CWE-120": "buffer-overflow",
    "CWE-416": "use-after-free",
    "CWE-190": "integer-overflow",
    "CWE-327": "crypto-weak",
    "CWE-798": "hardcoded-secret",
    "CWE-338": "insecure-random",
    "CWE-287": "improper-auth",
    "CWE-306": "missing-auth",
    "CWE-269": "privilege-escalation",
    "CWE-362": "race-condition",
}


class SarifNormalizer:
    def normalize(
        self,
        log: SarifLog,
        *,
        repo_id: str,
        snapshot_id: str,
        git_sha: str | None,
        worktree_snapshot_id: str | None = None,
        run_id: str | None = None,
        analyser_hint: str | None = None,
        ruleset_id: str | None = None,
        ruleset_name: str | None = None,
        raw_sarif_artifact_ref: ArtifactRef | None = None,
        produced_by_run_id: str | None = None,
    ) -> NormalizedSarifRun:
        if not log.runs:
            run_id = run_id or f"sarif:{uuid.uuid4().hex}"
            return NormalizedSarifRun(
                run_id=run_id,
                repo_id=repo_id,
                snapshot_id=snapshot_id,
                git_sha=git_sha,
                worktree_snapshot_id=worktree_snapshot_id,
                analyser_id=analyser_hint or "external",
                analyser_name=analyser_hint or "external",
                ruleset_id=ruleset_id or "ruleset:empty",
                rules=[],
                alerts=[],
                invocation_diagnostics=log.diagnostics,
                raw_sarif_artifact_ref=raw_sarif_artifact_ref,
                produced_by_run_id=produced_by_run_id,
            )
        sarif_run = log.runs[0]
        driver = sarif_run.tool.driver
        analyser_name = analyser_hint or driver.name
        analyser_id = _analyser_id(analyser_name)
        run_id = run_id or f"sarif:{uuid.uuid4().hex}"
        raw_rules = {rule.id: rule for component in [driver, *sarif_run.tool.extensions] for rule in component.rules}
        rules: dict[str, NormalizedRule] = {}
        alerts: list[NormalizedAlert] = []
        for result in sarif_run.results:
            rule = _rule_for_result(result, raw_rules)
            rule_id = result.rule_id or (rule.id if rule else f"unknown:{result.rule_index or 0}")
            normalized_rule = self.normalize_rule(rule_id, analyser_id, result, rule)
            rules.setdefault(rule_id, normalized_rule)
            alerts.append(self.normalize_alert(run_id, analyser_id, normalized_rule, result))
        inv = sarif_run.invocations[0] if sarif_run.invocations else None
        return NormalizedSarifRun(
            run_id=run_id,
            repo_id=repo_id,
            snapshot_id=snapshot_id,
            git_sha=git_sha,
            worktree_snapshot_id=worktree_snapshot_id,
            analyser_id=analyser_id,
            analyser_version=driver.semantic_version or driver.version,
            analyser_name=driver.name,
            ruleset_id=ruleset_id or stable_ruleset_id(list(rules.values())),
            ruleset_name=ruleset_name,
            invocation_start_ts=inv.start_time_utc if inv else None,
            invocation_end_ts=inv.end_time_utc if inv else None,
            invocation_exit_code=inv.exit_code if inv else None,
            invocation_successful=bool(inv.tool_execution_successful) if inv and inv.tool_execution_successful is not None else True,
            rules=list(rules.values()),
            alerts=alerts,
            invocation_diagnostics=[*log.diagnostics, *([n.message for n in inv.tool_execution_notifications] if inv else [])],
            raw_sarif_artifact_ref=raw_sarif_artifact_ref,
            produced_by_run_id=produced_by_run_id,
        )

    def normalize_rule(self, rule_id: str, analyser_id: str, result: SarifResult | None, rule: SarifReportingDescriptor | None) -> NormalizedRule:
        properties = {**(rule.properties if rule else {}), **(result.properties if result else {})}
        tags = sorted(set(_as_list(properties.get("tags")) + _as_list(properties.get("precision"))))
        cwe_ids = extract_cwe_ids(properties, tags)
        raw_level = (result.level if result else None) or (rule.default_configuration.level if rule and rule.default_configuration else None)
        severity = normalize_severity(analyser_id, raw_level, properties)
        family = normalize_rule_family(rule_id, tags=tags, cwe_ids=cwe_ids, description=(rule.short_description if rule else None) or "")
        return NormalizedRule(
            rule_id=rule_id,
            analyser_id=analyser_id,
            name=rule.name if rule else None,
            short_description=rule.short_description if rule else None,
            full_description=rule.full_description if rule else None,
            help_uri=rule.help_uri if rule else None,
            raw_severity=raw_level,
            normalized_severity=severity,
            cwe_ids=cwe_ids,
            owasp_categories=[tag for tag in tags if str(tag).lower().startswith("owasp")],
            rule_family=family,
            predicate_id=extract_predicate_id(analyser_id, rule_id, result.properties if result else {}),
            tags=tags,
            enabled=rule.default_configuration.enabled if rule and rule.default_configuration else True,
            confidence_level=_confidence_from_properties(analyser_id, properties),
            properties=properties,
        )

    def normalize_alert(self, run_id: str, analyser_id: str, rule: NormalizedRule, result: SarifResult) -> NormalizedAlert:
        primary = _location(result.locations[0]) if result.locations else AlertLocation()
        snippet = _snippet(result.locations[0]) if result.locations else None
        fingerprint = compute_alert_fingerprint(analyser_id=analyser_id, rule_id=rule.rule_id, file_path=primary.file_path, message=result.message, snippet=snippet)
        partial = compute_partial_fingerprint(rule_family=rule.rule_family, normalized_severity=rule.normalized_severity, start_column=primary.start_column)
        suppression = result.suppressions[0] if result.suppressions else None
        return NormalizedAlert(
            alert_id=f"{analyser_id}:{fingerprint}",
            run_id=run_id,
            rule_id=rule.rule_id,
            analyser_id=analyser_id,
            raw_level=result.level,
            normalized_severity=normalize_severity(analyser_id, result.level, {**rule.properties, **result.properties}),
            message=result.message,
            file_path=primary.file_path,
            start_line=primary.start_line,
            start_column=primary.start_column,
            end_line=primary.end_line,
            end_column=primary.end_column,
            related_locations=[_location(loc) for loc in result.related_locations],
            code_flows=[_code_flow(flow) for flow in result.code_flows],
            suppressed=bool(suppression),
            suppression_kind=suppression.kind if suppression else None,
            suppression_status=suppression.status if suppression else None,
            suppression_justification=suppression.justification if suppression else None,
            fingerprint=fingerprint,
            partial_fingerprint=partial,
            raw_fingerprints={**result.fingerprints, **result.partial_fingerprints},
            baseline_state=result.baseline_state,
            properties=result.properties,
        )


def normalize_severity(analyser_id: str, raw_level: str | None, properties: dict) -> NormalizedSeverity:
    cvss = _cvss(properties.get("security-severity") or properties.get("security_severity"))
    if cvss is not None:
        if cvss >= 9.0:
            return NormalizedSeverity.CRITICAL
        if cvss >= 7.0:
            return NormalizedSeverity.HIGH
        if cvss >= 4.0:
            return NormalizedSeverity.MEDIUM
        return NormalizedSeverity.LOW
    analyser = analyser_id.lower()
    level = (raw_level or properties.get("severity") or properties.get("problem.severity") or "warning").lower()
    if analyser == "bandit":
        severity = str(properties.get("issue_severity") or properties.get("severity") or level).upper()
        confidence = str(properties.get("issue_confidence") or properties.get("confidence") or "").upper()
        if severity == "HIGH" and confidence == "HIGH":
            return NormalizedSeverity.HIGH
        if severity == "HIGH" or (severity == "MEDIUM" and confidence == "HIGH"):
            return NormalizedSeverity.MEDIUM
        return NormalizedSeverity.LOW
    if analyser == "sonarqube":
        return {
            "blocker": NormalizedSeverity.CRITICAL,
            "critical": NormalizedSeverity.HIGH,
            "major": NormalizedSeverity.MEDIUM,
            "minor": NormalizedSeverity.LOW,
            "info": NormalizedSeverity.INFORMATIONAL,
        }.get(level, NormalizedSeverity.MEDIUM)
    if analyser == "semgrep":
        return {"error": NormalizedSeverity.HIGH, "warning": NormalizedSeverity.MEDIUM, "info": NormalizedSeverity.LOW, "note": NormalizedSeverity.INFORMATIONAL, "none": NormalizedSeverity.INFORMATIONAL}.get(level, NormalizedSeverity.MEDIUM)
    if analyser == "codeql":
        return {"error": NormalizedSeverity.HIGH, "warning": NormalizedSeverity.MEDIUM, "recommendation": NormalizedSeverity.LOW, "note": NormalizedSeverity.INFORMATIONAL}.get(level, NormalizedSeverity.MEDIUM)
    return {"error": NormalizedSeverity.HIGH, "warning": NormalizedSeverity.MEDIUM, "note": NormalizedSeverity.LOW, "none": NormalizedSeverity.INFORMATIONAL, "info": NormalizedSeverity.INFORMATIONAL}.get(level, NormalizedSeverity.MEDIUM)


def extract_cwe_ids(properties: dict, tags: Iterable[str] = ()) -> list[str]:
    values = []
    for key in ("cwe", "cwe-id", "cwe_ids", "cwe-ids", "tags"):
        values.extend(_as_list(properties.get(key)))
    values.extend(tags)
    found: set[str] = set()
    for value in values:
        for match in re.findall(r"(?i)cwe[-:\s]?(\d+)|\b(\d{1,4})\b", str(value)):
            number = next(part for part in match if part)
            found.add(f"CWE-{int(number)}")
    return sorted(found)


def normalize_rule_family(rule_id: str, *, tags: Iterable[str] = (), cwe_ids: Iterable[str] = (), description: str = "") -> str:
    for cwe in cwe_ids:
        if cwe in CWE_FAMILIES:
            return CWE_FAMILIES[cwe]
    haystack = " ".join([rule_id, description, *[str(tag) for tag in tags]]).lower()
    patterns = {
        "sql-injection": ("sqli", "sql.injection", "sql-injection", "sql injection", "cwe-89"),
        "xss": ("xss", "cross-site scripting", "cwe-79"),
        "path-traversal": ("path-traversal", "path traversal", "cwe-22"),
        "command-injection": ("command-injection", "command injection", "shell injection", "cwe-78"),
        "null-deref": ("null-deref", "null deref", "null pointer", "cwe-476"),
        "hardcoded-secret": ("hardcoded-secret", "hardcoded password", "hardcoded secret", "b105", "b106", "b107", "cwe-798"),
        "crypto-weak": ("weak crypto", "md5", "sha1", "cwe-327"),
        "buffer-overflow": ("buffer-overflow", "buffer overflow", "cwe-120"),
        "taint-flow": ("taint", "dataflow"),
    }
    for family, needles in patterns.items():
        if any(needle in haystack for needle in needles):
            return family
    return "other"


def extract_predicate_id(analyser_id: str, rule_id: str, properties: dict) -> str | None:
    if analyser_id == "bandit":
        return f"BANDIT-{rule_id}" if re.fullmatch(r"B\d{3}", rule_id) else rule_id
    if analyser_id == "semgrep":
        return rule_id
    for key in ("github/alertNumber", "alertNumber", "predicate_id", "precision"):
        if key in properties and key != "precision":
            return str(properties[key])
    if analyser_id == "codeql":
        return rule_id
    return None


def stable_ruleset_id(rules: list[NormalizedRule]) -> str:
    basis = "\n".join(sorted(f"{rule.analyser_id}:{rule.rule_id}:{rule.normalized_severity.value}" for rule in rules))
    return f"ruleset:{stable_hash(basis or 'empty', length=16)}"


def artifact_ref_for_raw_sarif(path: str, *, sha256: str | None, size_bytes: int | None) -> ArtifactRef:
    return ArtifactRef(artifact_id=f"art:sarif:{stable_hash(path + ':' + (sha256 or ''), length=16)}", kind=ArtifactKind.SARIF, uri=path, sha256=sha256, size_bytes=size_bytes, media_type="application/sarif+json", redaction_status=RedactionStatus.REDACTED, created_ts=_now_ts())


def _rule_for_result(result: SarifResult, rules: dict[str, SarifReportingDescriptor]) -> SarifReportingDescriptor | None:
    if result.rule_id and result.rule_id in rules:
        return rules[result.rule_id]
    if result.rule_index is not None:
        rule_values = list(rules.values())
        if 0 <= result.rule_index < len(rule_values):
            return rule_values[result.rule_index]
    return None


def _location(location: SarifLocation) -> AlertLocation:
    physical = location.physical_location
    region = physical.region if physical else None
    artifact = physical.artifact_location if physical else None
    return AlertLocation(
        file_path=artifact.resolved_path if artifact else None,
        start_line=region.start_line if region else None,
        start_column=region.start_column if region else None,
        end_line=region.end_line if region else None,
        end_column=region.end_column if region else None,
        message=location.message,
    )


def _code_flow(flow: SarifCodeFlow) -> AlertCodeFlow:
    locations = []
    for thread in flow.thread_flows:
        for item in thread.locations:
            if item.location:
                locations.append(_location(item.location))
    return AlertCodeFlow(locations=locations, message=flow.message)


def _snippet(location: SarifLocation) -> str | None:
    physical = location.physical_location
    region = physical.region if physical else None
    return region.snippet_text if region else None


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return [str(value)]


def _cvss(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _analyser_id(value: str) -> str:
    lowered = value.lower()
    if "semgrep" in lowered:
        return "semgrep"
    if "bandit" in lowered:
        return "bandit"
    if "codeql" in lowered:
        return "codeql"
    if "sonar" in lowered:
        return "sonarqube"
    return re.sub(r"[^a-z0-9_.-]+", "-", lowered).strip("-") or "external"


def _confidence_from_properties(analyser_id: str, properties: dict) -> str:
    if analyser_id == "codeql" and str(properties.get("precision", "")).lower() in {"very-high", "high"}:
        return "parser"
    return "parser"

