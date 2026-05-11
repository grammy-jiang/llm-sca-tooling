# Blast Radius

Private blast-radius analysis template.

Use `get_graph_slice`, `find_callers`, `find_callees`, and
`trace_cross_language` to estimate the impact scope of a proposed patch.

Workflow:
1. Extract files and symbols touched by the diff.
2. Traverse callers and callees up to depth 3.
3. Identify cross-language FFI and interface boundaries.
4. Produce a ranked impact list with confidence scores.
5. Flag any security-sensitive or release-blocking symbols in the blast radius.

Do not expand scope beyond the graph-connected component of the touched files.
