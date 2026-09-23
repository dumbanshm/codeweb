import express from "express";
import session from "express-session";
import fs from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import { randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";
import { simpleGit } from "simple-git";
import { analyzeCodebase } from "./analyzer.js";
import { checkNeo4jConnection, closeNeo4j, isNeo4jConfigured, loadEnvFromFile, readGraph, writeGraph, clearGraph } from "./neo4j.js";
import { checkRateLimit, getClientKey } from "./limiter.js";
import { explainWithLlm, isLlmConfigured } from "./llm.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "..");

const MAX_PORT_ATTEMPTS = 20;

await loadEnvFromFile(path.join(projectRoot, ".env"));

const app = express();
// Render (and most PaaS hosts) terminate TLS at the edge and forward plain HTTP
// internally. Without this, Express never sees the request as secure, so
// express-session's `cookie.secure: true` (set below under NODE_ENV=production)
// silently refuses to ever send the session cookie — every request looks like
// a brand-new anonymous session, breaking anything that reads back a graph
// that was just analyzed (code viewer, explain-node).
app.set("trust proxy", 1);
const port = Number(process.env.PORT || 3000);
let activePort = port;

const MAX_SNIPPET_CHARS = 500000;  // No practical limit — frontend handles scrolling
const PREVIEW_LINE_WINDOW = 40;

function hasGraphData(graph) {
  const nodeCount = graph?.nodes?.length || 0;
  const edgeCount = graph?.edges?.length || 0;
  return nodeCount > 0 && edgeCount > 0;
}

const emptyGraph = {
  rootPath: null,
  githubMeta: null,
  generatedAt: null,
  summary: { fileCount: 0, entityCount: 0, moduleCount: 0, edgeCount: 0 },
  nodes: [],
  edges: []
};

async function getGraphSnapshot(sessionId) {
  const storedGraph = await readGraph(sessionId);
  if (storedGraph?.nodes?.length) {
    return storedGraph;
  }

  return emptyGraph;
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
app.use(session({
  secret: process.env.SESSION_SECRET || "codeweb-secret-key-123",
  resave: false,
  saveUninitialized: true,
  cookie: { secure: process.env.NODE_ENV === "production" }
}));
app.use(express.static(path.join(projectRoot, "public")));

app.get("/api/health", async (req, res) => {
  const neo4jStatus = await checkNeo4jConnection();
  const graph = await getGraphSnapshot(req.sessionID);

  res.json({
    ok: true,
    neo4jConfigured: isNeo4jConfigured(),
    neo4jReachable: neo4jStatus.reachable,
    neo4jMessage: neo4jStatus.message || null,
    neo4jDatabase: neo4jStatus.database || null,
    analyzedRoot: graph.rootPath,
    sessionId: req.sessionID
  });
});

const MAX_REPO_SIZE_KB = Number(process.env.MAX_REPO_SIZE_KB || 20000); // 20MB, via GitHub API's reported repo size
const CLONE_TIMEOUT_MS = Number(process.env.CLONE_TIMEOUT_MS || 20000);

async function checkGithubRepoSize(owner, repo) {
  const apiUrl = `https://api.github.com/repos/${owner}/${repo}`;
  const response = await fetch(apiUrl, {
    headers: { "User-Agent": "codeweb-analyzer", Accept: "application/vnd.github+json" }
  });

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("Repository not found or not public.");
    }
    // GitHub API rate-limited or unreachable — don't block analysis on this alone,
    // the clone timeout + analyzer caps are the hard backstop.
    return { checked: false };
  }

  const data = await response.json();
  if (typeof data.size === "number" && data.size > MAX_REPO_SIZE_KB) {
    throw new Error(`Repository is too large to analyze (${Math.round(data.size / 1024)}MB, limit ${Math.round(MAX_REPO_SIZE_KB / 1024)}MB).`);
  }
  return { checked: true, sizeKb: data.size };
}

async function cloneWithTimeout(git, cloneUrl, tempRoot, timeoutMs) {
  let timedOut = false;
  const timeout = new Promise((_, reject) => {
    setTimeout(() => {
      timedOut = true;
      reject(new Error(`Clone timed out after ${Math.round(timeoutMs / 1000)}s.`));
    }, timeoutMs);
  });

  await Promise.race([git.clone(cloneUrl, tempRoot, ["--depth", "1"]), timeout]);
  if (timedOut) {
    throw new Error("Clone timed out.");
  }
}

let analysisInFlight = false;

app.post("/api/analyze-github", async (req, res) => {
  if (!checkRateLimit(getClientKey(req), "analyze-github")) {
    return res.status(429).json({ error: "Too many analysis requests. Please wait a bit and try again." });
  }

  const { url } = req.body;
  if (!url || typeof url !== "string") {
    return res.status(400).json({ error: "Missing or invalid repository URL" });
  }

  const match = url.match(/github\.com\/([^\/]+)\/([^\/]+?)(?:\.git|\/|$)/);
  if (!match) {
    return res.status(400).json({ error: "Invalid GitHub URL format" });
  }

  if (analysisInFlight) {
    return res.status(429).json({ error: "Another analysis is already running. Please try again shortly." });
  }

  const owner = match[1];
  const repo = match[2];

  const tempDirId = randomUUID();
  const tempRoot = path.join(os.tmpdir(), "codeweb", tempDirId);

  analysisInFlight = true;
  try {
    await checkGithubRepoSize(owner, repo);

    const git = simpleGit({
      env: { ...process.env, GIT_TERMINAL_PROMPT: '0' }
    });
    await fs.mkdir(path.join(os.tmpdir(), "codeweb"), { recursive: true });

    // Clone repo ephemerally, bounded by a timeout so one huge/slow repo can't hang the instance.
    console.log(`[GitHub] Attempting to clone ${owner}/${repo}...`);
    await cloneWithTimeout(git, `https://github.com/${owner}/${repo}.git`, tempRoot, CLONE_TIMEOUT_MS);

    const graph = await analyzeCodebase(tempRoot);

    let branch = "main";
    try {
      const headContent = await fs.readFile(path.join(tempRoot, ".git", "HEAD"), "utf8");
      const match = headContent.match(/ref:\s+refs\/heads\/(.+)/);
      if (match && match[1]) {
        branch = match[1].trim();
      }
    } catch (e) {
      console.warn("Could not determine precise default github branch. Defaulting to main.");
    }

    graph.githubMeta = { owner, repo, branch };

    const persistence = await writeGraph(graph, req.sessionID);

    res.json({
      ...graph,
      persistence
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    res.status(500).json({
      error: "GitHub analysis failed",
      message
    });
  } finally {
    analysisInFlight = false;
    try {
      await fs.rm(tempRoot, { recursive: true, force: true });
    } catch (rmError) {
      console.error(`Failed to delete temp dir ${tempRoot}:`, rmError);
    }
  }
});

app.get("/api/graph", async (req, res) => {
  try {
    const storedGraph = await readGraph(req.sessionID);
    if (storedGraph && hasGraphData(storedGraph)) {
      res.json({ source: "neo4j", ...storedGraph });
      return;
    }

    // No graph available for this session
    res.json({ source: "none", ...emptyGraph });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    res.json({ source: "none", ...emptyGraph, warning: message });
  }
});

// Shared by /api/node-details and /api/explain-node: resolves a node id to
// its metadata plus a (possibly truncated) source snippet.
async function getNodeContext(graph, nodeId) {
  const node = (graph.nodes || []).find((candidate) => candidate.id === nodeId);
  if (!node) {
    return { notFound: true };
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
    return { details, snippet: null, snippetMode: "none" };
  }

  let absoluteFilePath = "";
  let content = "";

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
      return {
        details,
        absoluteFilePath,
        snippet: "Error fetching from GitHub: " + err.message,
        snippetMode: "error"
      };
    }
  } else {
    absoluteFilePath = path.join(graph.rootPath, details.filePath);
    content = await fs.readFile(absoluteFilePath, "utf8");
  }

  const totalLines = content.split("\n").length;
  const startLine = details.line || 1;
  const endLine = details.endLine || (details.line ? details.line : totalLines);
  const snippetInfo = buildSnippet(content, startLine, endLine);

  return {
    details,
    absoluteFilePath,
    snippet: snippetInfo.snippet,
    snippetMode: snippetInfo.mode,
    snippetStartLine: snippetInfo.startLine,
    snippetEndLine: snippetInfo.endLine,
    previewReason: snippetInfo.previewReason || null
  };
}

app.get("/api/node-details", async (req, res) => {
  const nodeId = req.query?.id;

  if (!nodeId || typeof nodeId !== "string") {
    res.status(400).json({ error: "Missing required query param: id" });
    return;
  }

  try {
    const graph = await getGraphSnapshot(req.sessionID);
    const result = await getNodeContext(graph, nodeId);

    if (result.notFound) {
      res.status(404).json({ error: "Node not found", id: nodeId });
      return;
    }

    const { details, ...rest } = result;
    res.json({ ...details, ...rest });
  } catch (error) {
    console.error(`[node-details] CRASH:`, error);
    res.status(500).json({
      error: "Could not load node details",
      message: error instanceof Error ? error.message : String(error)
    });
  }
});

// Up to ~150 lines of the definition itself, plus signatures (not full source)
// of its direct callers/callees/imports, keeps the prompt small and cheap.
const EXPLAIN_MAX_SNIPPET_LINES = 150;
const EXPLAIN_MAX_NEIGHBORS = 10;

function buildNeighborSummaries(graph, nodeId) {
  const nodesById = new Map((graph.nodes || []).map((n) => [n.id, n]));
  const neighbors = [];

  for (const edge of graph.edges || []) {
    if (edge.type !== "CALLS" && edge.type !== "IMPORTS") continue;
    let relation = null;
    let neighborId = null;
    if (edge.from === nodeId) { relation = edge.type === "CALLS" ? "calls" : "imports"; neighborId = edge.to; }
    else if (edge.to === nodeId) { relation = edge.type === "CALLS" ? "called by" : "imported by"; neighborId = edge.from; }
    if (!neighborId) continue;

    const neighborNode = nodesById.get(neighborId);
    const label = neighborNode
      ? (neighborNode.qualifiedName || neighborNode.name || neighborNode.label || neighborNode.path || neighborId)
      : neighborId;

    neighbors.push({ relation, label, type: neighborNode?.type || "unknown" });
    if (neighbors.length >= EXPLAIN_MAX_NEIGHBORS) break;
  }

  return neighbors;
}

function truncateSnippetForPrompt(snippet) {
  if (!snippet) return snippet;
  const lines = snippet.split("\n");
  if (lines.length <= EXPLAIN_MAX_SNIPPET_LINES) return snippet;
  return lines.slice(0, EXPLAIN_MAX_SNIPPET_LINES).join("\n") + "\n... (truncated)";
}

const explanationCache = new Map(); // key: `${sessionId}:${nodeId}` -> explanation string

app.post("/api/explain-node", async (req, res) => {
  if (!isLlmConfigured()) {
    return res.status(503).json({ error: "AI explanations are not configured on this server." });
  }

  if (!checkRateLimit(getClientKey(req), "explain-node")) {
    return res.status(429).json({ error: "Too many explanation requests. Please wait a bit and try again." });
  }

  const nodeId = req.body?.nodeId;
  if (!nodeId || typeof nodeId !== "string") {
    return res.status(400).json({ error: "Missing required field: nodeId" });
  }

  const cacheKey = `${req.sessionID}:${nodeId}`;
  const cached = explanationCache.get(cacheKey);
  if (cached) {
    return res.json({ explanation: cached, cached: true });
  }

  try {
    const graph = await getGraphSnapshot(req.sessionID);

    // Only ever explain a node that's actually part of this session's own analyzed
    // graph — keeps this from being usable as a free-form prompt sandbox.
    const result = await getNodeContext(graph, nodeId);
    if (result.notFound) {
      return res.status(404).json({ error: "Node not found in the current graph", id: nodeId });
    }

    if (result.details.type === "module" || result.details.type === "project" || !result.snippet || result.snippetMode === "error") {
      return res.status(400).json({ error: "This node type doesn't have source code to explain." });
    }

    const neighbors = buildNeighborSummaries(graph, nodeId);
    const neighborLines = neighbors.length
      ? neighbors.map((n) => `- ${n.label} (${n.type}) — ${n.relation}`).join("\n")
      : "(no direct callers/callees/imports found)";

    const systemPrompt = "You are a senior engineer explaining unfamiliar code to a colleague. Be concise (3-5 sentences), concrete, and avoid restating the code line-by-line. If the snippet was truncated, don't call attention to it.";
    const userPrompt = [
      `File: ${result.details.filePath}`,
      `Name: ${result.details.name} (${result.details.type})`,
      "",
      "Source:",
      "```",
      truncateSnippetForPrompt(result.snippet),
      "```",
      "",
      "Direct relationships in the dependency graph:",
      neighborLines,
      "",
      "Explain what this does and why it's likely called/used, grounded in the relationships above."
    ].join("\n");

    const explanation = await explainWithLlm(systemPrompt, userPrompt);
    explanationCache.set(cacheKey, explanation);

    res.json({ explanation, cached: false });
  } catch (error) {
    console.error(`[explain-node] CRASH:`, error);
    res.status(502).json({
      error: "Could not generate explanation",
      message: error instanceof Error ? error.message : String(error)
    });
  }
});

app.get("*", (req, res) => {
  if (req.path.startsWith("/api/")) {
    return res.status(404).json({ error: "API endpoint not found", path: req.path });
  }
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

// Ensure clean slate on boot so old repos don't appear
await clearGraph();

const server = await startServerWithPortFallback(port);

// Startup analysis removed — graph populates on demand

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, async () => {
    server.close(async () => {
      await closeNeo4j();
      process.exit(0);
    });
  });
}
