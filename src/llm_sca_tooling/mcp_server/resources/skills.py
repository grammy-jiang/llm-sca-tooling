"""Repository skill-template MCP resources."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from llm_sca_tooling.mcp_server.context import McpRequestContext
from llm_sca_tooling.mcp_server.errors import ResourceNotFound
from llm_sca_tooling.mcp_server.resource_registry import (
    ResourceDescriptor,
    ResourceHandler,
    ResourceResult,
)
from llm_sca_tooling.mcp_server.resource_uris import ParsedResourceUri
from llm_sca_tooling.mcp_server.resources.core import _resource_result
from llm_sca_tooling.schemas.base import SCHEMA_VERSION, JsonObject
from llm_sca_tooling.skill_templates.bundled import (
    AGENT_HARNESS_SKILLS,
    PRODUCT_SKILLS,
)

_PRODUCT_SKILLS_DIR = ".skills"
_AGENT_SKILLS_DIR = ".agent/skills"
_BUNDLED_SKILLS_MODULE = "llm_sca_tooling.skill_templates.bundled"


@dataclass(frozen=True)
class SkillTemplate:
    name: str
    source: str
    origin: str
    path: str
    description: str
    version: str | None
    content: str

    def summary(self) -> JsonObject:
        payload: JsonObject = {
            "name": self.name,
            "source": self.source,
            "origin": self.origin,
            "path": self.path,
            "description": self.description,
        }
        if self.version:
            payload["version"] = self.version
        return payload

    def detail(self) -> JsonObject:
        payload = self.summary()
        payload["content"] = self.content
        return payload


class SkillsResource(ResourceHandler):
    descriptor = ResourceDescriptor(
        uri_template="code-intelligence://skills",
        name="skills",
        description="Repository-local workflow and harness skill templates.",
        schema_family="skill-template-list",
        freshness="workspace-file",
    )

    def matches(self, parsed: ParsedResourceUri) -> bool:
        return parsed.authority == "skills" and not parsed.segments

    def read(
        self, context: McpRequestContext, uri: str, parsed: ParsedResourceUri
    ) -> ResourceResult:
        del context, parsed
        skills = _load_skills()
        return _resource_result(
            uri,
            {
                "schema_version": SCHEMA_VERSION,
                "root_path": Path.cwd().as_posix(),
                "skill_dirs": [_PRODUCT_SKILLS_DIR, _AGENT_SKILLS_DIR],
                "package_skill_source": _BUNDLED_SKILLS_MODULE,
                "skills": [skill.summary() for skill in skills],
                "count": len(skills),
            },
        )


class SkillTemplateResource(ResourceHandler):
    descriptor = ResourceDescriptor(
        uri_template="code-intelligence://skills/{name}",
        name="skill-template",
        description="Repository-local skill template content by skill name.",
        schema_family="skill-template",
        freshness="workspace-file",
        size_class="bounded-text",
    )

    def matches(self, parsed: ParsedResourceUri) -> bool:
        return parsed.authority == "skills" and len(parsed.segments) == 1

    def read(
        self, context: McpRequestContext, uri: str, parsed: ParsedResourceUri
    ) -> ResourceResult:
        del context
        requested = _normalise_name(parsed.segments[0])
        matches = [
            skill
            for skill in _load_skills()
            if _normalise_name(skill.name) == requested
        ]
        if not matches:
            raise ResourceNotFound(f"skill template not found: {parsed.segments[0]}")
        product_matches = [skill for skill in matches if skill.source == "product"]
        preferred = product_matches[0] if product_matches else matches[0]
        return _resource_result(
            uri,
            {
                "schema_version": SCHEMA_VERSION,
                "name": preferred.name,
                "preferred": preferred.detail(),
                "variants": [skill.detail() for skill in matches],
            },
        )


def _load_skills(root: Path | None = None) -> list[SkillTemplate]:
    repo_root = root or Path.cwd()
    skills: list[SkillTemplate] = []
    workspace_product = _load_product_skills(repo_root / _PRODUCT_SKILLS_DIR, repo_root)
    packaged_product = _load_packaged_product_skills()
    workspace_agent = _load_agent_skills(repo_root / _AGENT_SKILLS_DIR, repo_root)
    packaged_agent = _load_packaged_agent_skills()
    skills.extend(_merge_by_name(workspace_product, packaged_product))
    skills.extend(_merge_by_name(workspace_agent, packaged_agent))
    return sorted(skills, key=lambda skill: (skill.name, skill.source, skill.path))


def _load_product_skills(skills_dir: Path, repo_root: Path) -> list[SkillTemplate]:
    if not skills_dir.is_dir():
        return []
    skills: list[SkillTemplate] = []
    for path in sorted(skills_dir.glob("*.SKILL.md")):
        if path.name.startswith("_"):
            continue
        content = path.read_text(encoding="utf-8")
        metadata = _front_matter(content)
        raw_metadata = metadata.get("metadata")
        nested_metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
        name = str(metadata.get("name") or path.name.removesuffix(".SKILL.md"))
        description = str(metadata.get("description") or _first_body_sentence(content))
        version_value = nested_metadata.get("version") or metadata.get("version")
        version = str(version_value) if version_value is not None else None
        skills.append(
            SkillTemplate(
                name=_normalise_name(name),
                source="product",
                origin="workspace",
                path=path.relative_to(repo_root).as_posix(),
                description=description.strip(),
                version=version,
                content=content,
            )
        )
    return skills


def _load_agent_skills(skills_dir: Path, repo_root: Path) -> list[SkillTemplate]:
    if not skills_dir.is_dir():
        return []
    skills: list[SkillTemplate] = []
    for path in sorted(skills_dir.glob("*/SKILL.md")):
        content = path.read_text(encoding="utf-8")
        skills.append(
            SkillTemplate(
                name=_normalise_name(path.parent.name),
                source="agent-harness",
                origin="workspace",
                path=path.relative_to(repo_root).as_posix(),
                description=_first_body_sentence(content),
                version=None,
                content=content,
            )
        )
    return skills


def _load_packaged_product_skills() -> list[SkillTemplate]:
    skills: list[SkillTemplate] = []
    for name, content in sorted(PRODUCT_SKILLS.items()):
        if not name.endswith(".SKILL.md") or name.startswith("_"):
            continue
        metadata = _front_matter(content)
        raw_metadata = metadata.get("metadata")
        nested_metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
        skill_name = str(metadata.get("name") or name.removesuffix(".SKILL.md"))
        description = str(metadata.get("description") or _first_body_sentence(content))
        version_value = nested_metadata.get("version") or metadata.get("version")
        version = str(version_value) if version_value is not None else None
        skills.append(
            SkillTemplate(
                name=_normalise_name(skill_name),
                source="product",
                origin="package",
                path=f"package:{_BUNDLED_SKILLS_MODULE}:PRODUCT_SKILLS[{name}]",
                description=description.strip(),
                version=version,
                content=content,
            )
        )
    return skills


def _load_packaged_agent_skills() -> list[SkillTemplate]:
    skills: list[SkillTemplate] = []
    for name, content in sorted(AGENT_HARNESS_SKILLS.items()):
        if not name.endswith("/SKILL.md"):
            continue
        skill_name = name.removesuffix("/SKILL.md")
        skills.append(
            SkillTemplate(
                name=_normalise_name(skill_name),
                source="agent-harness",
                origin="package",
                path=f"package:{_BUNDLED_SKILLS_MODULE}:AGENT_HARNESS_SKILLS[{name}]",
                description=_first_body_sentence(content),
                version=None,
                content=content,
            )
        )
    return skills


def _merge_by_name(
    primary: list[SkillTemplate], fallback: list[SkillTemplate]
) -> list[SkillTemplate]:
    merged = list(primary)
    seen = {_normalise_name(skill.name) for skill in primary}
    merged.extend(
        skill for skill in fallback if _normalise_name(skill.name) not in seen
    )
    return merged


def _front_matter(content: str) -> dict[str, Any]:
    if not content.startswith("---\n"):
        return {}
    end = content.find("\n---", 4)
    if end == -1:
        return {}
    yaml = YAML(typ="safe")
    parsed = yaml.load(content[4:end]) or {}
    return parsed if isinstance(parsed, dict) else {}


def _first_body_sentence(content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped == "---":
            continue
        if stripped.startswith("name:") or stripped.startswith("description:"):
            continue
        return stripped
    return ""


def _normalise_name(name: str) -> str:
    return name.strip().replace("_", "-").lower()
