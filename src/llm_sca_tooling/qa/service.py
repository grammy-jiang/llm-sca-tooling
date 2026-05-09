"""Repo-QA orchestration service used by MCP tools."""

from __future__ import annotations

from llm_sca_tooling.indexing.hashing import hash_text
from llm_sca_tooling.qa.answer import RepoAnswer
from llm_sca_tooling.qa.behaviour_trace import BEHAVIOUR_UNCERTAINTY, BehaviourTraceEngine
from llm_sca_tooling.qa.classifier import ClassificationResult, classify_question
from llm_sca_tooling.qa.confidence import CONFIDENCE_RANK, ConfidenceLabel
from llm_sca_tooling.qa.evidence_assembler import EvidenceAssembler
from llm_sca_tooling.qa.graph_query import GraphPathBuilder
from llm_sca_tooling.qa.interface_lookup import InterfaceContractLookup
from llm_sca_tooling.qa.lookup import FileLocLookup, GraphNodeRef, LookupResult, SymbolLocLookup
from llm_sca_tooling.qa.question import QuestionClass, RepoQuestion, normalize_question
from llm_sca_tooling.qa.ship_gate import AnswerQualityGate, read_ship_gate_config
from llm_sca_tooling.qa.synthesis import EvidenceSummary, NullSynthesisAdapter, SynthesisInput, SynthesisMode
from llm_sca_tooling.storage.workspace import WorkspaceStore


class RepoQAService:
    def __init__(self, workspace: WorkspaceStore) -> None:
        self.workspace = workspace

    def classify(self, question_text: str, *, repos: list[str] | None = None, use_llm_fallback: bool = False) -> tuple[RepoQuestion, ClassificationResult]:
        question = normalize_question(question_text, repos=repos)
        return question, classify_question(question, use_llm_fallback=use_llm_fallback)

    def answer(
        self,
        question_text: str,
        *,
        repos: list[str] | None = None,
        question_class_hint: str | None = None,
        synthesis: bool = True,
        synthesis_mode: str | None = None,
        max_evidence: int = 20,
        max_hops: int = 8,
        snapshot: str | None = None,
        include_blame: bool = False,
        budget: dict | None = None,
    ) -> RepoAnswer:
        question = normalize_question(question_text, repos=repos, snapshot_hint=snapshot)
        classification = classify_question(question)
        question_class = QuestionClass(question_class_hint) if question_class_hint else classification.question_class
        repo_ids = self._repo_ids(repos or question.repos)
        assembler = EvidenceAssembler()
        evidence = []
        graph_paths = []
        interface_contracts = []
        graph_nodes: list[GraphNodeRef] = []
        uncertainty = None
        recommended_action = None

        if question_class == QuestionClass.FILE_LOC:
            lookup = FileLocLookup(self.workspace.graph).lookup(question, repo_ids, snapshot_id=snapshot)
            evidence.extend(assembler.from_lookup(lookup, limit=max_evidence))
            graph_nodes.extend(lookup.matched_nodes)
        elif question_class == QuestionClass.SYMBOL_LOC:
            lookup = SymbolLocLookup(self.workspace.graph).lookup(question, repo_ids, snapshot_id=snapshot)
            evidence.extend(assembler.from_lookup(lookup, limit=max_evidence))
            graph_nodes.extend(lookup.matched_nodes)
            interface_lookup = InterfaceContractLookup(self.workspace)
            for ref in lookup.matched_nodes:
                interface_contracts.extend(interface_lookup.lookup_by_symbol_ref(ref))
            evidence.extend(assembler.from_interfaces(interface_contracts, limit=max_evidence - len(evidence)))
        elif question_class == QuestionClass.BEHAVIOUR_TRACE:
            gate_config = read_ship_gate_config(self.workspace)
            trace = BehaviourTraceEngine(self.workspace.graph).trace(question, repo_ids, max_hops=max_hops, behaviour_gate_met=gate_config.behaviour_trace_gate_met)
            graph_paths = trace.graph_paths
            evidence.extend(assembler.from_graph_paths(graph_paths, limit=max_evidence))
            uncertainty = trace.uncertainty
            if trace.unknown_reason:
                recommended_action = _recommended_action(trace.unknown_reason)
        elif question_class == QuestionClass.CONTRACT_CHECK:
            interface_contracts = InterfaceContractLookup(self.workspace).lookup(question, repo_id=repo_ids[0] if len(repo_ids) == 1 else None)
            evidence.extend(assembler.from_interfaces(interface_contracts, limit=max_evidence))
            for contract in interface_contracts:
                graph_nodes.extend(contract.server_node_refs + contract.client_node_refs)
            if graph_nodes:
                links = []
                builder = GraphPathBuilder(self.workspace.graph)
                for ref in graph_nodes:
                    links.extend(builder.find_document_links(ref.node_id))
                evidence.extend(assembler.from_document_links(links, limit=max_evidence - len(evidence)))
        else:
            lookup = FileLocLookup(self.workspace.graph).lookup(question, repo_ids, snapshot_id=snapshot)
            evidence.extend(assembler.from_lookup(lookup, limit=max_evidence))
            graph_nodes.extend(lookup.matched_nodes)
            uncertainty = "Question class OTHER is handled as best-effort supporting evidence."

        confidence, reason, action = assembler.derive_confidence(question_class, evidence)
        if question_class == QuestionClass.BEHAVIOUR_TRACE and evidence:
            confidence = ConfidenceLabel.HEURISTIC
            uncertainty = uncertainty or BEHAVIOUR_UNCERTAINTY
        recommended_action = recommended_action or action
        graph_node_ids = sorted({item.node_id for item in evidence if item.node_id and item.node_id.startswith("node:")} | {ref.node_id for ref in graph_nodes})
        if not graph_node_ids and confidence in {ConfidenceLabel.PARSER, ConfidenceLabel.ANALYSER}:
            confidence = ConfidenceLabel.HEURISTIC
            reason = f"{reason}; downgraded because no graph node citations were available"
        if confidence == ConfidenceLabel.UNKNOWN and not recommended_action:
            recommended_action = "Run `graph_build` to index this repository."
        answer_text, synthesis_model, synthesis_tokens = self._answer_text(question, question_class, evidence, graph_nodes, graph_paths, interface_contracts, synthesis=synthesis and not _budget_disables_synthesis(budget), synthesis_mode=synthesis_mode)
        answer = RepoAnswer(
            answer_id=f"answer:{hash_text(question.question_id + ':' + question_class.value, length=24)}",
            question_id=question.question_id,
            question_class=question_class,
            answer_text=answer_text,
            confidence=confidence,
            confidence_reason=reason,
            evidence=evidence[:max_evidence],
            graph_node_ids=graph_node_ids,
            graph_paths=graph_paths,
            interface_contracts=interface_contracts,
            blame_entries=None,
            uncertainty=uncertainty,
            recommended_action=recommended_action,
            synthesis_mode=synthesis_mode if synthesis else None,
            synthesis_model=synthesis_model,
            synthesis_tokens=synthesis_tokens,
            run_event_ids=[],
            snapshot_ids=self._snapshot_ids(graph_node_ids),
        )
        return AnswerQualityGate().apply(answer, read_ship_gate_config(self.workspace))

    def _repo_ids(self, repos: list[str] | None) -> list[str]:
        if repos:
            return [self.workspace.repositories.get_repo(repo).repo_id for repo in repos]
        return [repo.repo_id for repo in self.workspace.repositories.list_repos(active_only=True)]

    def _answer_text(self, question: RepoQuestion, question_class: QuestionClass, evidence, graph_nodes, graph_paths, interface_contracts, *, synthesis: bool, synthesis_mode: str | None) -> tuple[str, str | None, int | None]:
        if not synthesis:
            if evidence:
                return f"Found {len(evidence)} evidence item(s) for {question_class.value}.", None, None
            return "No graph-backed evidence was found for this question.", None, None
        summary = EvidenceSummary(
            source_count=len(evidence),
            highest_evidence_confidence=max((item.confidence for item in evidence), key=lambda confidence: CONFIDENCE_RANK[confidence], default=ConfidenceLabel.UNKNOWN),
            has_graph_path=bool(graph_paths),
            has_interface_contract=bool(interface_contracts),
            has_blame_chain=False,
            question_class_threshold_met=False,
        )
        output = NullSynthesisAdapter().synthesize(
            SynthesisInput(
                question_class=question_class,
                normalized_question=question.normalized_text,
                evidence_summary=summary,
                graph_nodes=graph_nodes,
                graph_paths=graph_paths,
                interface_contracts=interface_contracts,
                max_tokens=512,
                mode=SynthesisMode(synthesis_mode or SynthesisMode.TECHNICAL_SUMMARY.value),
            )
        )
        return output.answer_text, output.synthesis_model, output.synthesis_tokens_used

    def _snapshot_ids(self, graph_node_ids: list[str]) -> dict[str, str]:
        result = {}
        for node_id in graph_node_ids:
            node = self.workspace.graph.fetch_node(node_id)
            if node:
                result[node.repo.repo_id] = node.snapshot.worktree_snapshot_id or node.snapshot.git_sha or node.snapshot.captured_ts
        return result


def _budget_disables_synthesis(budget: dict | None) -> bool:
    if not budget:
        return False
    max_tokens = budget.get("max_tokens")
    return isinstance(max_tokens, int) and max_tokens < 256


def _recommended_action(reason: str) -> str:
    if reason in {"no_start_node_resolved", "no_trigger_tokens"}:
        return "Provide more specific code token in the question."
    if reason == "no_path_found":
        return "Run `graph_build` to index this repository."
    return "Check if the behaviour-trace ship-gate threshold has been met."
