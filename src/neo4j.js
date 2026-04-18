import neo4j from "neo4j-driver";

function parseEnvFile(contents) {
  const values = {};
  for (const rawLine of contents.split("\n")) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) {
      continue;
    }
    const separatorIndex = line.indexOf("=");
    if (separatorIndex === -1) {
      continue;
    }
    const key = line.slice(0, separatorIndex).trim();
    const value = line.slice(separatorIndex + 1).trim();
    values[key] = value;
  }
  return values;
}

export async function loadEnvFromFile(filePath) {
  try {
    const fs = await import("node:fs/promises");
    const contents = await fs.readFile(filePath, "utf8");
    const values = parseEnvFile(contents);
    for (const [key, value] of Object.entries(values)) {
      if (!process.env[key]) {
        process.env[key] = value;
      }
    }
  } catch {
    return;
  }
}

function getNeo4jConfig() {
  const { NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE } = process.env;
  if (!NEO4J_URI || !NEO4J_USERNAME || !NEO4J_PASSWORD) {
    return null;
  }
  return {
    uri: NEO4J_URI,
    username: NEO4J_USERNAME,
    password: NEO4J_PASSWORD,
    database: NEO4J_DATABASE || "neo4j"
  };
}

let driver;

function summarizeGraph(nodes, edges) {
  return {
    fileCount: nodes.filter((node) => node.type === "file").length,
    entityCount: nodes.filter((node) => node.type === "function" || node.type === "class" || node.type === "method").length,
    moduleCount: nodes.filter((node) => node.type === "module").length,
    edgeCount: edges.length
  };
}

export function isNeo4jConfigured() {
  return Boolean(getNeo4jConfig());
}

export async function checkNeo4jConnection() {
  const config = getNeo4jConfig();
  const activeDriver = getDriver();

  if (!config || !activeDriver) {
    return {
      configured: false,
      reachable: false,
      message: "Neo4j environment variables are not configured."
    };
  }

  const session = activeDriver.session({ database: config.database });
  try {
    await session.run("RETURN 1 AS ok");
    return {
      configured: true,
      reachable: true,
      database: config.database
    };
  } catch (error) {
    return {
      configured: true,
      reachable: false,
      database: config.database,
      message: error instanceof Error ? error.message : String(error)
    };
  } finally {
    await session.close();
  }
}

function getDriver() {
  const config = getNeo4jConfig();
  if (!config) {
    return null;
  }

  if (!driver) {
    driver = neo4j.driver(config.uri, neo4j.auth.basic(config.username, config.password));
  }

  return driver;
}

export async function writeGraph(graph) {
  const config = getNeo4jConfig();
  const activeDriver = getDriver();

  if (!config || !activeDriver) {
    return { persisted: false, reason: "Neo4j environment variables are not configured." };
  }

  const session = activeDriver.session({ database: config.database });

  try {
    await session.executeWrite(async (tx) => {
      await tx.run("MATCH (n) DETACH DELETE n");

      // Group nodes by specific label for batched insertion
      const nodesByLabel = {
        Project: [],
        File: [],
        Module: [],
        Entity: []
      };

      for (const node of graph.nodes) {
        if (node.type === "project") nodesByLabel.Project.push(node);
        else if (node.type === "file") nodesByLabel.File.push(node);
        else if (node.type === "module") nodesByLabel.Module.push(node);
        else nodesByLabel.Entity.push(node);
      }

      for (const [label, nodes] of Object.entries(nodesByLabel)) {
        if (nodes.length === 0) continue;
        await tx.run(
          `UNWIND $nodes AS node
           MERGE (n:GraphNode:${label} {id: node.id})
           SET n += node`,
          { nodes }
        );
      }

      // Group edges by type for batched insertion
      const edgesByType = {};
      for (const edge of graph.edges) {
        const type = edge.type.replace(/[^A-Z_]/g, "_");
        if (!edgesByType[type]) edgesByType[type] = [];
        edgesByType[type].push(edge);
      }

      for (const [type, edges] of Object.entries(edgesByType)) {
        if (edges.length === 0) continue;
        await tx.run(
          `UNWIND $edges AS edge
           MATCH (from {id: edge.from})
           MATCH (to {id: edge.to})
           MERGE (from)-[r:${type} {id: edge.id}]->(to)
           SET r += edge`,
          { edges }
        );
      }
    });

    return { persisted: true };
  } catch (error) {
    return {
      persisted: false,
      reason: error instanceof Error ? `Neo4j write failed: ${error.message}` : "Neo4j write failed."
    };
  } finally {
    await session.close();
  }
}

export async function readGraph() {
  const config = getNeo4jConfig();
  const activeDriver = getDriver();

  if (!config || !activeDriver) {
    return null;
  }

  const session = activeDriver.session({ database: config.database });

  try {
    const nodesResult = await session.run(
      "MATCH (n) RETURN properties(n) AS node ORDER BY coalesce(n.path, n.label, n.name)"
    );
    const edgesResult = await session.run(
      "MATCH (a)-[r]->(b) RETURN properties(r) AS edge ORDER BY r.type, r.id"
    );

    const nodes = nodesResult.records.map((record) => record.get("node"));
    const edges = edgesResult.records.map((record) => record.get("edge"));
    const projectNode = nodes.find((node) => node.type === "project");

    return {
      rootPath: projectNode?.path || null,
      generatedAt: null,
      summary: summarizeGraph(nodes, edges),
      nodes,
      edges
    };
  } catch {
    return null;
  } finally {
    await session.close();
  }
}

export async function closeNeo4j() {
  if (driver) {
    await driver.close();
    driver = undefined;
  }
}
