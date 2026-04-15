import express from "express";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { analyzeCodebase } from "./analyzer.js";
import { closeNeo4j, isNeo4jConfigured, loadEnvFromFile, readGraph, writeGraph } from "./neo4j.js";

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
  generatedAt: null,
  summary: { fileCount: 0, entityCount: 0, moduleCount: 0, edgeCount: 0 },
  nodes: [],
  edges: []
};

const MAX_SNIPPET_CHARS = 4500;
const PREVIEW_LINE_WINDOW = 40;

async function getDefaultGraph() {
  const defaultRoot = process.env.TARGET_CODEBASE || sampleCodebasePath;

  if (lastGraph.nodes.length > 0 && lastGraph.rootPath === defaultRoot) {
    return lastGraph;
  }

  const graph = await analyzeCodebase(defaultRoot);
  await writeGraph(graph);
  lastGraph = graph;
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

app.get("/api/health", (_req, res) => {
  res.json({
    ok: true,
    neo4jConfigured: isNeo4jConfigured(),
    analyzedRoot: lastGraph.rootPath,
    defaultRoot: process.env.TARGET_CODEBASE || sampleCodebasePath
  });
});

app.post("/api/analyze", async (req, res) => {
  const requestedRoot = req.body?.rootPath || process.env.TARGET_CODEBASE || sampleCodebasePath;

  try {
    const graph = await analyzeCodebase(requestedRoot);
    const persistence = await writeGraph(graph);
    lastGraph = graph;

    res.json({
      ...graph,
      persistence
    });
  } catch (error) {
    res.status(500).json({
      error: "Analysis failed",
      message: error instanceof Error ? error.message : String(error)
    });
  }
});

app.get("/api/graph", async (_req, res) => {
  try {
    const storedGraph = await readGraph();
    if (storedGraph) {
      res.json({
        source: "neo4j",
        ...storedGraph
      });
      return;
    }

    if (lastGraph.nodes.length === 0) {
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
    try {
      const graph = await getDefaultGraph();
      res.json({
        source: "generated-fallback",
        ...graph,
        warning: error instanceof Error ? error.message : String(error)
      });
    } catch (fallbackError) {
      res.status(500).json({
        error: "Could not load graph",
        message: fallbackError instanceof Error ? fallbackError.message : String(fallbackError)
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

    const absoluteFilePath = path.join(graph.rootPath, details.filePath);
    const content = await fs.readFile(absoluteFilePath, "utf8");
    const snippetInfo = buildSnippet(content, details.line || 1, details.endLine || details.line || 1);

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
