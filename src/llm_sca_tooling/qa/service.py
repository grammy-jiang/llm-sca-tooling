"""Repo-QA orchestration service."""

from __future__ import annotations

from collections.abc import Sequence

from llm_sca_tooling.plugins.registry import PluginRegistry
from llm_sca_tooling.plugins.store import InterfaceRecordStore
from llm_sca_tooling.plugins.traversal import CrossLanguageTraverser
from llm_sca_tooling.qa.answer import RepoAnswer, make_answer_id, recommended_action
from llm_sca_tooling.qa.behaviour_trace import trace_behaviour
from llm_sca_tooling.qa.classifier import classify_question
from llm_sca_tooling.qa.confidence import derive_confidence
from llm_sca_tooling.qa.evidence_assembler import EvidenceAssembler
from llm_sca_tooling.qa.graph_query import GraphPath
from llm_sca_tooling.qa.interface_lookup import InterfaceContractResult
from llm_sca_tooling.qa.lookup import GraphNodeRef, lookup_files, lookup_symbols
from llm_sca_tooling.qa.question import QuestionClass, normalize_question
from llm_sca_tooling.qa.ship_gate import AnswerQualityGate, ShipGateConfig
from llm_sca_tooling.qa.synthesis import (
    NullSynthesisAdapter,
    SynthesisInput,
    SynthesisMode,
    evidence_summary,
)
from llm_sca_tooling.storage.graph_queries import GraphQueryStore
from llm_sca_tooling.storage.workspace import WorkspaceStore

__all__ = ["answer_repo_question"]


async def answer_repo_question(
    workspace: WorkspaceStore,
    graph: GraphQueryStore,
    *,
    question: str,
    repos: list[str] | None = None,
    question_class_hint: str | None = None,
    synthesis: bool = True,
    synthesis_mode: str | None = None,
    max_evidence: int = 20,
    max_hops: int = 8,
    snapshot: str | None = None,
    registry: PluginRegistry | None = None,
    interface_store: InterfaceRecordStore | None = None,
    gate_config: ShipGateConfig | None = None,
) -> RepoAnswer:
    repo_question = normalize_question(question, repos=repos, snapshot_hint=snapshot)
    classification = classify_question(repo_question, use_llm_fallback=False)
    klass = (
        QuestionClass(question_class_hint)
        if question_class_hint is not None
        else classification.question_class
    )
    assembler = EvidenceAssembler()
    node_refs: list[GraphNodeRef] = []
    graph_paths: list[GraphPath] = []
    interface_contracts: list[InterfaceContractResult] = []
    if klass == QuestionClass.file_loc:
        lookup = await lookup_files(workspace, repo_question, repos)
        node_refs = lookup.matched_nodes
        evidence = assembler.from_lookup(lookup)
    elif klass == QuestionClass.symbol_loc:
        lookup = await lookup_symbols(workspace, repo_question, repos)
        node_refs = lookup.matched_nodes
        evidence = assembler.from_lookup(lookup)
    elif klass == QuestionClass.behaviour_trace:
        traverser = CrossLanguageTraverser(registry, workspace) if registry else None
        trace = await trace_behaviour(
            workspace, repo_question, traverser, max_hops=max_hops
        )
        graph_paths = trace.graph_paths
        evidence = assembler.from_graph_paths(graph_paths)
    elif klass == QuestionClass.contract_check:
        interface_contracts = []
        evidence = []
        if interface_store is not None:
            records = await interface_store.list_records()
            for record in records[:max_evidence]:
                evidence.append(
                    assembler.from_interface_contracts(
                        [
                            InterfaceContractResult(
                                interface_record=record,
                                matched_operations=list(record.operations),
                                confidence=record.confidence,
                                snapshot_ids=record.snapshot_ids,
                            )
                        ]
                    )[0]
                )
    else:
        lookup = await lookup_files(workspace, repo_question, repos)
        node_refs = lookup.matched_nodes
        evidence = assembler.from_lookup(lookup)
    evidence = evidence[:max_evidence]
    confidence, reason, uncertainty = derive_confidence(klass, evidence)
    text = _answer_text(klass, evidence)
    synth_model: str | None = None
    synth_tokens: int | None = None
    if synthesis and evidence:
        mode = SynthesisMode(synthesis_mode or SynthesisMode.technical_summary.value)
        output = NullSynthesisAdapter().synthesize(
            SynthesisInput(
                question_class=klass,
                normalized_question=repo_question.normalized_text,
                evidence_summary=evidence_summary(evidence),
                graph_nodes=node_refs,
                graph_paths=graph_paths,
                interface_contracts=interface_contracts,
                mode=mode,
            )
        )
        text = output.answer_text
        synth_model = output.synthesis_model
        synth_tokens = output.synthesis_tokens_used
    answer = RepoAnswer(
        answer_id=make_answer_id(repo_question.question_id, evidence),
        question_id=repo_question.question_id,
        question_class=klass,
        answer_text=text,
        confidence=confidence,
        confidence_reason=reason,
        evidence=evidence,
        graph_node_ids=[ev.node_id for ev in evidence if ev.node_id],
        graph_paths=graph_paths,
        interface_contracts=interface_contracts,
        uncertainty=uncertainty,
        recommended_action=(
            recommended_action(klass) if confidence == "unknown" else None
        ),
        synthesis_mode=synthesis_mode if synthesis else None,
        synthesis_model=synth_model,
        synthesis_tokens=synth_tokens,
        run_event_ids=["qa:classification", "qa:ship_gate"],
        snapshot_ids={repo: snapshot for repo in repos or [] if snapshot},
    )
    return AnswerQualityGate().apply(answer, gate_config or ShipGateConfig())


def _answer_text(klass: QuestionClass, evidence: Sequence[object]) -> str:
    if not evidence:
        return f"No {klass.value} evidence found."
    return f"Found {len(evidence)} {klass.value} evidence item(s)."
