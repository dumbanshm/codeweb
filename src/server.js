import express from "express";
import fs from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import { randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";
import { simpleGit } from "simple-git";
import { analyzeCodebase } from "./analyzer.js";
import { checkNeo4jConnection, closeNeo4j, isNeo4jConfigured, loadEnvFromFile, readGraph, writeGraph } from "./neo4j.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "..");
const sampleCodebasePath = path.join(projectRoot, "sample codebase");
const MAX_PORT_ATTEMPTS = 20;

await loadEnvFromFile(path.join(projectRoot, ".env"));

const app = express();
const port = Number(process.env.PORT || 3000);
let activePort = port;

let lastGraph = {
  rootPath: null,
  githubMeta: null,
  generatedAt: null,
  summary: { fileCount: 0, entityCount: 0, moduleCount: 0, edgeCount: 0 },
  nodes: [],
  edges: []
};
let startupError = null;
let lastPersistence = null;

const MAX_SNIPPET_CHARS = 4500;
const PREVIEW_LINE_WINDOW = 40;

function sanitizeEnvPath(value) {
  if (!value) {
    return "";
  }
  const trimmed = value.trim();
  return trimmed.replace(/^['"]|['"]$/g, "");
}

function resolveCodebasePath(rawPath) {
  const sanitized = sanitizeEnvPath(rawPath);
  if (!sanitized) {
    return sampleCodebasePath;
  }
  if (path.isAbsolute(sanitized)) {
    return sanitized;
  }
  return path.resolve(projectRoot, sanitized);
}

function hasGraphData(graph) {
  const nodeCount = graph?.nodes?.length || 0;
  const edgeCount = graph?.edges?.length || 0;
  return nodeCount > 0 && edgeCount > 0;
}

async function getDefaultGraph() {
  const defaultRoot = resolveCodebasePath(process.env.TARGET_CODEBASE);
  await fs.access(defaultRoot);

  if (lastGraph.nodes.length > 0 && lastGraph.rootPath === defaultRoot) {
    return lastGraph;
  }

  const graph = await analyzeCodebase(defaultRoot);
  lastPersistence = await writeGraph(graph);
  lastGraph = graph;
  startupError = null;
  return graph;
}

async function getGraphSnapshot() {
  if (lastGraph.nodes.length > 0) {
    return lastGraph;
  }

  const storedGraph = await readGraph();
  if (storedGraph?.nodes?.length) {
    return storedGraph;
  }

  return await getDefaultGraph();
}

function clampLine(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function buildSnippet(content, line, endLine) {
  const lines = content.split("\n");
  const totalLines = lines.length;
  const startLine = clampLine(line || 1, 1, totalLines);
  const safeEndLine = clampLine(endLine || startLine, startLine, totalLines);
  const fullSnippet = lines.slice(startLine - 1, safeEndLine).join("\n");

  if (fullSnippet.length <= MAX_SNIPPET_CHARS) {
    return {
      mode: "full",
      startLine,
      endLine: safeEndLine,
      snippet: fullSnippet
    };
  }

  const previewStart = clampLine(startLine - Math.floor(PREVIEW_LINE_WINDOW / 2), 1, totalLines);
  const previewEnd = clampLine(previewStart + PREVIEW_LINE_WINDOW, previewStart, totalLines);
  const previewSnippet = lines.slice(previewStart - 1, previewEnd).join("\n");

  return {
    mode: "preview",
    startLine: previewStart,
    endLine: previewEnd,
    snippet: previewSnippet,
    previewReason: "Definition is large, showing focused preview around declaration."
  };
}

app.use(express.json());
app.use(express.static(path.join(projectRoot, "public")));

app.get("/api/health", async (_req, res) => {
  const resolvedDefaultRoot = resolveCodebasePath(process.env.TARGET_CODEBASE);
  let defaultRootExists = false;

  try {
    await fs.access(resolvedDefaultRoot);
    defaultRootExists = true;
  } catch {
    defaultRootExists = false;
  }

  const neo4jStatus = await checkNeo4jConnection();

  res.json({
    ok: true,
    neo4jConfigured: isNeo4jConfigured(),
    neo4jReachable: neo4jStatus.reachable,
    neo4jMessage: neo4jStatus.message || null,
    neo4jDatabase: neo4jStatus.database || null,
    analyzedRoot: lastGraph.rootPath,
    defaultRoot: resolvedDefaultRoot,
    defaultRootExists,
    startupError,
    lastPersistence
  });
});

app.post("/api/analyze", async (req, res) => {
  const requestedRoot = resolveCodebasePath(req.body?.rootPath || process.env.TARGET_CODEBASE);

  try {
    await fs.access(requestedRoot);
    const graph = await analyzeCodebase(requestedRoot);
    const persistence = await writeGraph(graph);
    lastPersistence = persistence;
    lastGraph = graph;
    startupError = null;

    res.json({
      ...graph,
      persistence
    });
  } catch (error) {
    startupError = error instanceof Error ? error.message : String(error);
    res.status(500).json({
      error: "Analysis failed",
      message: startupError
    });
  }
});

app.post("/api/analyze-github", async (req, res) => {
  const { url } = req.body;
  if (!url || typeof url !== "string") {
    return res.status(400).json({ error: "Missing or invalid repository URL" });
  }

  const match = url.match(/github\.com\/([^\/]+)\/([^\/]+?)(?:\.git|\/|$)/);
  if (!match) {
    return res.status(400).json({ error: "Invalid GitHub URL format" });
  }

  const owner = match[1];
  const repo = match[2];
  
  const tempDirId = randomUUID();
  const tempRoot = path.join(os.tmpdir(), "codeweb", tempDirId);

  try {
    const git = simpleGit({
      env: { ...process.env, GIT_TERMINAL_PROMPT: '0' }
    });
    await fs.mkdir(path.join(os.tmpdir(), "codeweb"), { recursive: true });
    
    // Clone repo ephemerally
    console.log(`[GitHub] Attempting to clone ${owner}/${repo}...`);
    await git.clone(`https://github.com/${owner}/${repo}.git`, tempRoot, ["--depth", "1"]);

    const graph = await analyzeCodebase(tempRoot);
    
    const tempGit = simpleGit(tempRoot);
    const branchSummary = await tempGit.branchLocal();
    const branch = branchSummary.current || "main";
    
    graph.githubMeta = { owner, repo, branch };
    
    const persistence = await writeGraph(graph);
    lastPersistence = persistence;
    lastGraph = graph;
    startupError = null;

    res.json({
      ...graph,
      persistence
    });
  } catch (error) {
    startupError = error instanceof Error ? error.message : String(error);
    res.status(500).json({
      error: "GitHub analysis failed",
      message: startupError
    });
  } finally {
    try {
      await fs.rm(tempRoot, { recursive: true, force: true });
    } catch (rmError) {
      console.error(`Failed to delete temp dir ${tempRoot}:`, rmError);
    }
  }
});

app.get("/api/graph", async (_req, res) => {
  try {
    const storedGraph = await readGraph();
    if (storedGraph && hasGraphData(storedGraph)) {
      res.json({
        source: "neo4j",
        ...storedGraph
      });
      return;
    }

    if (lastGraph.nodes.length === 0 || !hasGraphData(lastGraph)) {
      const graph = await getDefaultGraph();
      res.json({
        source: "generated",
        ...graph
      });
      return;
    }

    res.json({
      source: "memory",
      ...lastGraph
    });
  } catch (error) {
    startupError = error instanceof Error ? error.message : String(error);
    try {
      const graph = await getDefaultGraph();
      res.json({
        source: "generated-fallback",
        ...graph,
        warning: startupError
      });
    } catch (fallbackError) {
      startupError = fallbackError instanceof Error ? fallbackError.message : String(fallbackError);
      res.status(500).json({
        error: "Could not load graph",
        message: startupError
      });
    }
  }
});

app.get("/api/node-details", async (req, res) => {
  const nodeId = req.query?.id;
  if (!nodeId || typeof nodeId !== "string") {
    res.status(400).json({ error: "Missing required query param: id" });
    return;
  }

  try {
    const graph = await getGraphSnapshot();
    const node = (graph.nodes || []).find((candidate) => candidate.id === nodeId);
    if (!node) {
      res.status(404).json({ error: "Node not found", id: nodeId });
      return;
    }

    const details = {
      id: node.id,
      type: node.type,
      name: node.qualifiedName || node.name || node.label || node.path || node.id,
      filePath: node.filePath || node.path || null,
      line: node.line || null,
      endLine: node.endLine || null,
      language: node.language || null
    };

    if (!graph.rootPath || !details.filePath || details.type === "module" || details.type === "project") {
      res.json({ ...details, snippet: null, snippetMode: "none" });
      return;
    }

    let absoluteFilePath = "";
    let content = "";
    let snippetInfo = null;

    if (graph.githubMeta) {
      const { owner, repo, branch } = graph.githubMeta;
      absoluteFilePath = `https://raw.githubusercontent.com/${owner}/${repo}/${branch}/${details.filePath}`;
      try {
        const fetchResponse = await fetch(absoluteFilePath);
        if (!fetchResponse.ok) {
          throw new Error(`GitHub returned ${fetchResponse.status}`);
        }
        content = await fetchResponse.text();
      } catch (err) {
        return res.json({
          ...details,
          absoluteFilePath,
          snippet: "Error fetching code snippet from GitHub: " + err.message,
          snippetMode: "none"
        });
      }
    } else {
      absoluteFilePath = path.join(graph.rootPath, details.filePath);
      content = await fs.readFile(absoluteFilePath, "utf8");
    }

    snippetInfo = buildSnippet(content, details.line || 1, details.endLine || details.line || 1);

    res.json({
      ...details,
      absoluteFilePath,
      snippet: snippetInfo.snippet,
      snippetMode: snippetInfo.mode,
      snippetStartLine: snippetInfo.startLine,
      snippetEndLine: snippetInfo.endLine,
      previewReason: snippetInfo.previewReason || null
    });
  } catch (error) {
    res.status(500).json({
      error: "Could not load node details",
      message: error instanceof Error ? error.message : String(error)
    });
  }
});

app.get("*", (_req, res) => {
  res.sendFile(path.join(projectRoot, "public", "index.html"));
});

async function startServerWithPortFallback(basePort) {
  return await new Promise((resolve, reject) => {
    let attempt = 0;

    const tryListen = () => {
      const candidatePort = basePort + attempt;
      const candidateServer = app
        .listen(candidatePort, () => {
          activePort = candidatePort;
          if (attempt > 0) {
            console.warn(`Port ${basePort} is busy. Using port ${candidatePort} instead.`);
          }
          console.log(`Dependency graph prototype running at http://localhost:${candidatePort}`);
          resolve(candidateServer);
        })
        .once("error", (error) => {
          if (error?.code === "EADDRINUSE" && attempt < MAX_PORT_ATTEMPTS) {
            attempt += 1;
            tryListen();
            return;
          }
          reject(error);
        });
    };

    tryListen();
  });
}

const server = await startServerWithPortFallback(port);

getDefaultGraph().catch((error) => {
  startupError = error instanceof Error ? error.message : String(error);
  console.error("Initial sample analysis failed:", error);
});

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, async () => {
    server.close(async () => {
      await closeNeo4j();
      process.exit(0);
    });
  });
}
