import fs from "node:fs/promises";
import path from "node:path";

const SUPPORTED_EXTENSIONS = new Set([".js", ".jsx", ".ts", ".tsx", ".py"]);
const IGNORED_DIRECTORIES = new Set([
  ".git",
  "node_modules",
  "dist",
  "build",
  ".next",
  ".turbo",
  ".venv",
  "venv",
  "__pycache__"
]);
const CALL_EXCLUDE = new Set([
  "if",
  "for",
  "while",
  "switch",
  "catch",
  "return",
  "typeof",
  "await",
  "new",
  "def",
  "class",
  "function",
  "constructor",
  "super",
  "print"
]);
const JS_METHOD_EXCLUDE = new Set(["if", "for", "while", "switch", "catch", "constructor", "get", "set"]);

function normalizePath(inputPath) {
  return inputPath.split(path.sep).join("/");
}

function toEntityId(filePath, qualifiedName) {
  return `${normalizePath(filePath)}::${qualifiedName}`;
}

function toModuleId(moduleName) {
  return `module::${moduleName}`;
}

function countLeadingSpaces(line) {
  return line.length - line.trimStart().length;
}

async function walkDirectory(rootPath, currentPath = rootPath, files = []) {
  const entries = await fs.readdir(currentPath, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = path.join(currentPath, entry.name);

    if (entry.isDirectory()) {
      if (!IGNORED_DIRECTORIES.has(entry.name)) {
        await walkDirectory(rootPath, fullPath, files);
      }
      continue;
    }

    if (SUPPORTED_EXTENSIONS.has(path.extname(entry.name))) {
      files.push(fullPath);
    }
  }

  return files;
}

function detectLanguage(filePath) {
  const extension = path.extname(filePath);
  if (extension === ".py") {
    return "python";
  }
  if (extension === ".ts" || extension === ".tsx") {
    return "typescript";
  }
  return "javascript";
}

function detectProjectName(rootPath) {
  return path.basename(rootPath) || rootPath;
}

function findPythonModuleTarget(moduleName, filesByRelativePath) {
  const normalized = normalizePath(moduleName.replace(/\./g, "/"));
  const candidates = [
    `${normalized}.py`,
    `${normalized}/__init__.py`
  ];

  for (const candidate of candidates) {
    if (filesByRelativePath.has(candidate)) {
      return candidate;
    }
  }

  return null;
}

function findJavaScriptImportTarget(fromFile, importPath, filesByRelativePath) {
  const sourceDir = path.posix.dirname(fromFile);
  const rawBase = importPath.startsWith("/")
    ? importPath.slice(1)
    : normalizePath(path.posix.normalize(path.posix.join(sourceDir, importPath)));

  const candidates = [];
  const extension = path.posix.extname(rawBase);

  if (extension) {
    candidates.push(rawBase);
  } else {
    candidates.push(rawBase);
    for (const supportedExtension of SUPPORTED_EXTENSIONS) {
      candidates.push(`${rawBase}${supportedExtension}`);
      candidates.push(`${rawBase}/index${supportedExtension}`);
    }
  }

  for (const candidate of candidates) {
    if (filesByRelativePath.has(candidate)) {
      return candidate;
    }
  }

  return null;
}

function resolveImportTarget(fromFile, importPath, language, filesByRelativePath) {
  if (language === "python") {
    return findPythonModuleTarget(importPath, filesByRelativePath);
  }

  if (importPath.startsWith(".") || importPath.startsWith("/")) {
    return findJavaScriptImportTarget(fromFile, importPath, filesByRelativePath);
  }

  return null;
}

function finalizeDefinitionEndLines(definitions, totalLines) {
  const sorted = [...definitions].sort((left, right) => left.line - right.line);

  for (let index = 0; index < sorted.length; index += 1) {
    const current = sorted[index];
    const next = sorted[index + 1];
    current.endLine = next ? Math.max(current.line, next.line - 1) : totalLines;
  }
}

function parsePythonStructure(content, relativePath, language) {
  const lines = content.split("\n");
  const definitions = [];
  const contextsByLine = new Array(lines.length + 1).fill(null);
  const scopeStack = [];

  for (let lineNumber = 1; lineNumber <= lines.length; lineNumber += 1) {
    const line = lines[lineNumber - 1];
    const trimmed = line.trim();
    const indent = countLeadingSpaces(line);

    while (scopeStack.length > 0 && indent <= scopeStack[scopeStack.length - 1].indent) {
      scopeStack.pop();
    }

    const classMatch = line.match(/^\s*class\s+([A-Za-z_]\w*)\s*(?:\(|:)/);
    if (classMatch) {
      const className = classMatch[1];
      const definition = {
        id: toEntityId(relativePath, className),
        name: className,
        qualifiedName: className,
        type: "class",
        language,
        filePath: relativePath,
        line: lineNumber,
        parent: relativePath
      };
      definitions.push(definition);
      scopeStack.push({ kind: "class", name: className, indent, definition });
      contextsByLine[lineNumber] = definition.id;
      continue;
    }

    const functionMatch = line.match(/^\s*def\s+([A-Za-z_]\w*)\s*\(/);
    if (functionMatch) {
      const functionName = functionMatch[1];
      const parentClass = [...scopeStack].reverse().find((scope) => scope.kind === "class");
      const qualifiedName = parentClass ? `${parentClass.name}.${functionName}` : functionName;
      const type = parentClass ? "method" : "function";
      const parent = parentClass ? parentClass.definition.id : relativePath;
      const definition = {
        id: toEntityId(relativePath, qualifiedName),
        name: functionName,
        qualifiedName,
        type,
        language,
        filePath: relativePath,
        line: lineNumber,
        parent
      };
      definitions.push(definition);
      scopeStack.push({ kind: type, name: qualifiedName, indent, definition });
      contextsByLine[lineNumber] = definition.id;
      continue;
    }

    const activeCallable = [...scopeStack].reverse().find((scope) => scope.kind === "function" || scope.kind === "method");
    if (!trimmed || trimmed.startsWith("#")) {
      contextsByLine[lineNumber] = activeCallable?.definition.id || null;
      continue;
    }

    contextsByLine[lineNumber] = activeCallable?.definition.id || null;
  }

  finalizeDefinitionEndLines(definitions, lines.length);
  return { definitions, contextsByLine };
}

function parseJavaScriptStructure(content, relativePath, language) {
  const lines = content.split("\n");
  const definitions = [];
  const contextsByLine = new Array(lines.length + 1).fill(null);
  const scopeStack = [];
  let braceDepth = 0;

  for (let lineNumber = 1; lineNumber <= lines.length; lineNumber += 1) {
    while (scopeStack.length > 0 && braceDepth < scopeStack[scopeStack.length - 1].depth) {
      scopeStack.pop();
    }

    const line = lines[lineNumber - 1];
    const trimmed = line.trim();
    const activeClass = [...scopeStack].reverse().find((scope) => scope.kind === "class");
    const activeCallable = [...scopeStack].reverse().find((scope) => scope.kind === "function" || scope.kind === "method");

    let definition = null;
    let definitionKind = null;

    const classMatch = line.match(/^\s*(?:export\s+)?class\s+([A-Za-z_$][\w$]*)\b/);
    const functionMatch = line.match(/^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(/);
    const arrowMatch = line.match(
      /^\s*(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>/
    );
    const functionExpressionMatch = line.match(
      /^\s*(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?function\b/
    );
    const methodMatch = activeClass && !activeCallable
      ? line.match(/^\s*(?:async\s+)?([A-Za-z_$][\w$]*)\s*\([^;]*\)\s*\{/)
      : null;

    if (classMatch) {
      const className = classMatch[1];
      definition = {
        id: toEntityId(relativePath, className),
        name: className,
        qualifiedName: className,
        type: "class",
        language,
        filePath: relativePath,
        line: lineNumber,
        parent: relativePath
      };
      definitionKind = "class";
    } else if (functionMatch || arrowMatch || functionExpressionMatch) {
      const functionName = functionMatch?.[1] || arrowMatch?.[1] || functionExpressionMatch?.[1];
      definition = {
        id: toEntityId(relativePath, functionName),
        name: functionName,
        qualifiedName: functionName,
        type: "function",
        language,
        filePath: relativePath,
        line: lineNumber,
        parent: relativePath
      };
      definitionKind = "function";
    } else if (methodMatch && !JS_METHOD_EXCLUDE.has(methodMatch[1])) {
      const methodName = methodMatch[1];
      const qualifiedName = `${activeClass.name}.${methodName}`;
      definition = {
        id: toEntityId(relativePath, qualifiedName),
        name: methodName,
        qualifiedName,
        type: "method",
        language,
        filePath: relativePath,
        line: lineNumber,
        parent: activeClass.definition.id
      };
      definitionKind = "method";
    }

    if (definition) {
      definitions.push(definition);
    }

    const openBraces = [...line.matchAll(/\{/g)].length;
    const closeBraces = [...line.matchAll(/\}/g)].length;
    braceDepth += openBraces - closeBraces;

    if (definition && openBraces > 0) {
      scopeStack.push({ kind: definitionKind, name: definition.qualifiedName, definition, depth: braceDepth });
    }

    if (!trimmed.startsWith("//") && !trimmed.startsWith("*")) {
      const callableAfterDefinition = definitionKind === "function" || definitionKind === "method" ? definition.id : activeCallable?.definition.id;
      contextsByLine[lineNumber] = callableAfterDefinition || null;
    }
  }

  finalizeDefinitionEndLines(definitions, lines.length);
  return { definitions, contextsByLine };
}

function parseStructure(content, absolutePath, relativePath) {
  const language = detectLanguage(absolutePath);
  const structure = language === "python"
    ? parsePythonStructure(content, relativePath, language)
    : parseJavaScriptStructure(content, relativePath, language);

  return {
    language,
    definitions: structure.definitions,
    contextsByLine: structure.contextsByLine
  };
}

function parseImports(content, relativePath, language, filesByRelativePath) {
  const imports = [];
  const moduleNodes = [];
  const seenEdgeIds = new Set();
  const seenModuleIds = new Set();
  const addModuleNode = (moduleName) => {
    const id = toModuleId(moduleName);
    if (seenModuleIds.has(id)) {
      return;
    }

    seenModuleIds.add(id);
    moduleNodes.push({
      id,
      name: moduleName,
      label: moduleName,
      type: "module",
      parent: null,
      path: moduleName
    });
  };

  const addImport = (rawImport, lineNumber) => {
    const resolvedTarget = resolveImportTarget(relativePath, rawImport, language, filesByRelativePath);
    const targetId = resolvedTarget || toModuleId(rawImport);

    if (!resolvedTarget) {
      addModuleNode(rawImport);
    }

    const edgeId = `${relativePath}::imports::${targetId}`;
    if (seenEdgeIds.has(edgeId)) {
      return;
    }

    seenEdgeIds.add(edgeId);
    imports.push({
      id: edgeId,
      from: relativePath,
      to: targetId,
      type: "IMPORTS",
      line: lineNumber,
      rawImport,
      resolved: Boolean(resolvedTarget)
    });
  };

  if (language === "python") {
    for (const match of content.matchAll(/^\s*from\s+([A-Za-z0-9_.]+)\s+import\s+.+$/gm)) {
      const line = content.slice(0, match.index).split("\n").length;
      addImport(match[1], line);
    }

    for (const match of content.matchAll(/^\s*import\s+([A-Za-z0-9_.,\s]+)$/gm)) {
      const line = content.slice(0, match.index).split("\n").length;
      const modules = match[1]
        .split(",")
        .map((moduleName) => moduleName.trim().split(/\s+as\s+/)[0])
        .filter(Boolean);
      for (const moduleName of modules) {
        addImport(moduleName, line);
      }
    }
  } else {
    for (const match of content.matchAll(/^\s*import\s+.+?\s+from\s+['"](.+?)['"]/gm)) {
      const line = content.slice(0, match.index).split("\n").length;
      addImport(match[1], line);
    }

    for (const match of content.matchAll(/^\s*import\s+['"](.+?)['"]/gm)) {
      const line = content.slice(0, match.index).split("\n").length;
      addImport(match[1], line);
    }

    for (const match of content.matchAll(/^\s*const\s+.+?=\s*require\(['"](.+?)['"]\)/gm)) {
      const line = content.slice(0, match.index).split("\n").length;
      addImport(match[1], line);
    }
  }

  return { imports, moduleNodes };
}

function parseCalls(content, relativePath, contextsByLine, definitionIndex) {
  const edges = [];
  const seen = new Set();

  for (const match of content.matchAll(/\b([A-Za-z_$][\w$]*)\s*\(/g)) {
    const name = match[1];
    if (CALL_EXCLUDE.has(name)) {
      continue;
    }

    const targets = definitionIndex.get(name) || [];
    if (targets.length === 0) {
      continue;
    }

    const line = content.slice(0, match.index).split("\n").length;
    const callerId = contextsByLine[line] || relativePath;

    for (const target of targets) {
      if (target.id === callerId) {
        continue;
      }

      const edgeId = `${callerId}::calls::${target.id}`;
      if (seen.has(edgeId)) {
        continue;
      }

      seen.add(edgeId);
      edges.push({
        id: edgeId,
        from: callerId,
        to: target.id,
        type: "CALLS",
        line
      });
    }
  }

  return edges;
}

function summarizeGraph(nodes, edges) {
  return {
    fileCount: nodes.filter((node) => node.type === "file").length,
    entityCount: nodes.filter((node) => node.type === "function" || node.type === "class" || node.type === "method").length,
    moduleCount: nodes.filter((node) => node.type === "module").length,
    edgeCount: edges.length
  };
}

export async function analyzeCodebase(rootPath) {
  const absoluteRoot = path.resolve(rootPath);
  const filesOnDisk = await walkDirectory(absoluteRoot);
  const projectId = `project::${normalizePath(absoluteRoot)}`;
  const projectLabel = detectProjectName(absoluteRoot);
  const filesByRelativePath = new Set(filesOnDisk.map((absolutePath) => normalizePath(path.relative(absoluteRoot, absolutePath))));
  const projectNode = {
    id: projectId,
    label: projectLabel,
    name: projectLabel,
    path: normalizePath(absoluteRoot),
    type: "project",
    parent: null
  };
  const fileNodes = [];
  const entityNodes = [];
  const moduleNodes = [];
  const containsEdges = [];
  const importEdges = [];
  const callEdges = [];
  const definitionIndex = new Map();
  const fileContents = [];
  const moduleNodeIndex = new Map();

  for (const absolutePath of filesOnDisk) {
    const relativePath = normalizePath(path.relative(absoluteRoot, absolutePath));
    const content = await fs.readFile(absolutePath, "utf8");
    const structure = parseStructure(content, absolutePath, relativePath);

    fileNodes.push({
      id: relativePath,
      path: relativePath,
      type: "file",
      language: structure.language,
      label: relativePath,
      name: path.basename(relativePath),
      parent: projectId
    });

    containsEdges.push({
      id: `${projectId}::contains::${relativePath}`,
      from: projectId,
      to: relativePath,
      type: "CONTAINS"
    });

    for (const definition of structure.definitions) {
      entityNodes.push({
        ...definition,
        label: definition.qualifiedName
      });
      containsEdges.push({
        id: `${definition.parent}::contains::${definition.id}`,
        from: definition.parent,
        to: definition.id,
        type: "CONTAINS"
      });

      const existing = definitionIndex.get(definition.name) || [];
      existing.push(definition);
      definitionIndex.set(definition.name, existing);
    }

    const parsedImports = parseImports(content, relativePath, structure.language, filesByRelativePath);
    importEdges.push(...parsedImports.imports);
    for (const moduleNode of parsedImports.moduleNodes) {
      if (!moduleNodeIndex.has(moduleNode.id)) {
        moduleNodeIndex.set(moduleNode.id, {
          ...moduleNode,
          parent: projectId
        });
      }
    }

    fileContents.push({
      relativePath,
      content,
      contextsByLine: structure.contextsByLine
    });
  }

  moduleNodes.push(...moduleNodeIndex.values());

  for (const file of fileContents) {
    callEdges.push(...parseCalls(file.content, file.relativePath, file.contextsByLine, definitionIndex));
  }

  const nodes = [projectNode, ...fileNodes, ...entityNodes, ...moduleNodes];
  const edges = [...containsEdges, ...callEdges, ...importEdges];

  return {
    rootPath: absoluteRoot,
    generatedAt: new Date().toISOString(),
    summary: summarizeGraph(nodes, edges),
    nodes,
    edges
  };
}
