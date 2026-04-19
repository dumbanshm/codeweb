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

const MAX_SNIPPET_CHARS = 500000;  // No practical limit — frontend handles scrolling
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
  if (!sanitized) return null;
  if (path.isAbsolute(sanitized)) return sanitized;
  return path.resolve(projectRoot, sanitized);
}

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

async function getGraphSnapshot() {
  if (lastGraph.nodes.length > 0) {
    return lastGraph;
  }

  const storedGraph = await readGraph();
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
    // Check Neo4j first
    const storedGraph = await readGraph();
    if (storedGraph && hasGraphData(storedGraph)) {
      res.json({ source: "neo4j", ...storedGraph });
      return;
    }

    // Check in-memory graph (from a previous GitHub analysis this session)
    if (lastGraph.nodes.length > 0 && hasGraphData(lastGraph)) {
      res.json({ source: "memory", ...lastGraph });
      return;
    }

    // No graph available — return empty state
    res.json({ source: "none", ...emptyGraph });
  } catch (error) {
    startupError = error instanceof Error ? error.message : String(error);
    res.json({ source: "none", ...emptyGraph, warning: startupError });
  }
});

app.get("/api/node-details", async (req, res) => {
  const nodeId = req.query?.id;
  console.log(`[node-details] Request for: ${nodeId}`);

  if (!nodeId || typeof nodeId !== "string") {
    console.log(`[node-details] REJECTED: missing id param`);
    res.status(400).json({ error: "Missing required query param: id" });
    return;
  }

  try {
    const graph = await getGraphSnapshot();
    console.log(`[node-details] Graph has ${graph.nodes?.length || 0} nodes, githubMeta: ${!!graph.githubMeta}, rootPath: ${graph.rootPath}`);

    const node = (graph.nodes || []).find((candidate) => candidate.id === nodeId);
    if (!node) {
      console.log(`[node-details] Node NOT FOUND: ${nodeId}`);
      res.status(404).json({ error: "Node not found", id: nodeId });
      return;
    }

    console.log(`[node-details] Found node: type=${node.type}, filePath=${node.filePath || node.path}, line=${node.line}`);

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
      console.log(`[node-details] Returning without snippet: rootPath=${!!graph.rootPath}, filePath=${details.filePath}, type=${details.type}`);
      res.json({ ...details, snippet: null, snippetMode: "none" });
      return;
    }

    let absoluteFilePath = "";
    let content = "";
    let snippetInfo = null;

    if (graph.githubMeta) {
      const { owner, repo, branch } = graph.githubMeta;
      absoluteFilePath = `https://raw.githubusercontent.com/${owner}/${repo}/${branch}/${details.filePath}`;
      console.log(`[node-details] Fetching from GitHub: ${absoluteFilePath}`);
      try {
        const fetchResponse = await fetch(absoluteFilePath);
        console.log(`[node-details] GitHub response: ${fetchResponse.status}`);
        if (!fetchResponse.ok) {
          throw new Error(`GitHub returned ${fetchResponse.status}`);
        }
        content = await fetchResponse.text();
        console.log(`[node-details] Got ${content.length} chars from GitHub`);
      } catch (err) {
        console.error(`[node-details] GitHub fetch FAILED:`, err.message);
        return res.json({
          ...details,
          absoluteFilePath,
          snippet: "Error fetching from GitHub: " + err.message,
          snippetMode: "error"
        });
      }
    } else {
      absoluteFilePath = path.join(graph.rootPath, details.filePath);
      console.log(`[node-details] Reading local file: ${absoluteFilePath}`);
      content = await fs.readFile(absoluteFilePath, "utf8");
      console.log(`[node-details] Got ${content.length} chars from local file`);
    }

    // For file-type nodes or nodes without line info, show the whole file
    const totalLines = content.split("\n").length;
    const startLine = details.line || 1;
    const endLine = details.endLine || (details.line ? details.line : totalLines);

    snippetInfo = buildSnippet(content, startLine, endLine);
    console.log(`[node-details] Snippet built: mode=${snippetInfo.mode}, lines ${snippetInfo.startLine}-${snippetInfo.endLine}, length=${snippetInfo.snippet.length}`);

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
    console.error(`[node-details] CRASH:`, error);
    res.status(500).json({
      error: "Could not load node details",
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
