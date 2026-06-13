// ts-morph runner for the TypeScript/JavaScript indexing backend.
//
// Reads a JSON request from stdin:
//   { "repoRoot": "<abs path>", "files": ["<abs path>", ...] }
// and writes a JSON facts object to stdout:
//   { "tsMorphVersion", "modules", "symbols", "imports", "calls", "diagnostics" }
//
// All paths in the output are repo-relative POSIX. Cross-file import and call
// targets are resolved through ts-morph's symbol/type resolution — the facts a
// regex parser cannot produce. The runner is resilient: a parse failure on one
// file is recorded in `diagnostics` and does not abort the run.

import { readFileSync } from "node:fs";
import { relative, sep } from "node:path";
import { Project, SyntaxKind, Node } from "ts-morph";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const tsMorphVersion = require("ts-morph/package.json").version;

function rel(repoRoot, abs) {
  return relative(repoRoot, abs).split(sep).join("/");
}

function readRequest() {
  const raw = readFileSync(0, "utf8");
  return JSON.parse(raw);
}

function main() {
  const { repoRoot, files } = readRequest();
  const project = new Project({
    skipAddingFilesFromTsConfig: true,
    skipFileDependencyResolution: false,
    compilerOptions: {
      allowJs: true,
      checkJs: false,
      noEmit: true,
      // resolve enough to link cross-file symbols without a tsconfig
      moduleResolution: 2, // NodeJs
    },
  });

  const out = {
    tsMorphVersion,
    modules: [],
    symbols: [],
    imports: [],
    calls: [],
    diagnostics: [],
  };

  // Set membership: only emit edges whose target is one of the indexed files.
  const inSet = new Set(files.map((f) => rel(repoRoot, f)));
  const sources = [];
  for (const abs of files) {
    try {
      sources.push(project.addSourceFileAtPath(abs));
    } catch (err) {
      out.diagnostics.push({ file: rel(repoRoot, abs), error: String(err) });
    }
  }

  for (const sf of sources) {
    const file = rel(repoRoot, sf.getFilePath());
    out.modules.push({ file });
    try {
      collectSymbols(sf, file, out);
      collectImports(sf, file, repoRoot, inSet, out);
      collectCalls(sf, file, repoRoot, inSet, out);
    } catch (err) {
      out.diagnostics.push({ file, error: String(err) });
    }
  }

  process.stdout.write(JSON.stringify(out));
}

function pushSymbol(out, file, name, kind, qualifiedName, node) {
  if (!name) return;
  out.symbols.push({
    file,
    name,
    kind,
    qualifiedName,
    startLine: node.getStartLineNumber(),
    endLine: node.getEndLineNumber(),
  });
}

function collectSymbols(sf, file, out) {
  for (const cls of sf.getClasses()) {
    const cname = cls.getName();
    pushSymbol(out, file, cname, "class", cname, cls);
    for (const m of cls.getMethods()) {
      const mname = m.getName();
      pushSymbol(out, file, mname, "method", `${cname ?? "?"}.${mname}`, m);
    }
  }
  for (const iface of sf.getInterfaces()) {
    const iname = iface.getName();
    pushSymbol(out, file, iname, "interface", iname, iface);
  }
  for (const fn of sf.getFunctions()) {
    const fname = fn.getName();
    pushSymbol(out, file, fname, "function", fname, fn);
  }
  for (const en of sf.getEnums()) {
    const ename = en.getName();
    pushSymbol(out, file, ename, "enum", ename, en);
  }
}

function collectImports(sf, file, repoRoot, inSet, out) {
  for (const imp of sf.getImportDeclarations()) {
    const target = imp.getModuleSpecifierSourceFile();
    if (!target) continue; // external / unresolved
    const targetRel = rel(repoRoot, target.getFilePath());
    if (inSet.has(targetRel)) {
      out.imports.push({ from: file, to: targetRel });
    }
  }
}

function enclosingSymbolName(node) {
  const fn = node.getFirstAncestor(
    (a) =>
      Node.isFunctionDeclaration(a) ||
      Node.isMethodDeclaration(a) ||
      Node.isFunctionExpression(a) ||
      Node.isArrowFunction(a),
  );
  if (!fn) return null;
  if (Node.isMethodDeclaration(fn)) {
    const cls = fn.getFirstAncestorByKind(SyntaxKind.ClassDeclaration);
    const cname = cls?.getName();
    const mname = fn.getName();
    return mname ? (cname ? `${cname}.${mname}` : mname) : null;
  }
  if (Node.isFunctionDeclaration(fn)) return fn.getName() ?? null;
  // named via variable declaration (const f = () => {} / function expr)
  const decl = fn.getFirstAncestorByKind(SyntaxKind.VariableDeclaration);
  return decl?.getName() ?? null;
}

function collectCalls(sf, file, repoRoot, inSet, out) {
  for (const call of sf.getDescendantsOfKind(SyntaxKind.CallExpression)) {
    const callerName = enclosingSymbolName(call);
    if (!callerName) continue;
    const expr = call.getExpression();
    let sym = expr.getSymbol();
    // Imported callees resolve to the local import alias; follow it to the
    // original declaration so the call edge points at the defining file.
    if (sym && typeof sym.getAliasedSymbol === "function") {
      const aliased = sym.getAliasedSymbol();
      if (aliased) sym = aliased;
    }
    const decls = sym?.getDeclarations() ?? [];
    if (decls.length === 0) continue;
    const decl = decls[0];
    const declSf = decl.getSourceFile();
    const targetRel = rel(repoRoot, declSf.getFilePath());
    if (!inSet.has(targetRel)) continue; // external/unindexed callee
    let calleeName = null;
    if (typeof decl.getName === "function") calleeName = decl.getName();
    if (!calleeName) {
      const named = decl.getFirstAncestorByKind?.(SyntaxKind.VariableDeclaration);
      calleeName = named?.getName() ?? null;
    }
    if (!calleeName) continue;
    if (targetRel === file && calleeName === callerName) continue; // self
    out.calls.push({
      from: { file, name: callerName },
      to: { file: targetRel, name: calleeName },
    });
  }
}

main();
