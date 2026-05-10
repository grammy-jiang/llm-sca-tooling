# Plugin Authoring Guide

Plugins should produce typed evidence rather than free-form text. A plugin should:

1. Declare its detector capability and supported file types.
2. Emit graph nodes and edges with provenance.
3. Attach diagnostics for partial or uncertain extraction.
4. Avoid network access unless an approved task-specific policy allows it.
5. Add focused tests under `tests/plugins/` or a domain-specific test folder.

Before release, include plugin behavior in a HarnessConditionSheet and make sure
the plugin does not weaken hard constraints HC1-HC6.

## Limitations

Plugins run inside the repository governance model. They should not install
global tools, mutate source files, or persist hidden state outside the workspace.
