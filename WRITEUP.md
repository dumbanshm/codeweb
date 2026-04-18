# CodeWeb - Codebase Dependency Graph

CodeWeb is an interactive prototype application designed to scan a codebase, map out its internal dependencies, and visualize the findings as a force-directed graph in the browser. It helps developers understand how different files, entities, and modules interact with each other.

---

## 🛠️ Tech Stack

- **Backend Context:** Node.js runtime
- **Web Framework:** Express.js (REST API & static file serving)
- **Database:** Neo4j (Graph Database, typically AuraDB for cloud hosting)
- **Frontend:** Vanilla HTML, CSS, and JavaScript (Client-side rendering & graph mapping)
- **Database Driver:** `neo4j-driver` (for Cypher querying)

---

## 🧩 How Each Part Works

### 1. The Analyzer (`src/analyzer.js`)
The core engine of the application. Given a target codebase directory, it parses the code to extract structural elements. It maps out:
- **Nodes:** Projects, Files, Entities (classes, functions, methods), and Modules.
- **Relationships (Edges):** `CONTAINS` (e.g., File contains a Function), `CALLS` (e.g., Function A calls Function B), and `IMPORTS` (e.g., File imports a Module).

### 2. The Database Manager (`src/neo4j.js`)
This module handles all communication with the Neo4j database. It uses the `neo4j-driver` to convert the analyzer's output into Cypher queries, pushing the nodes and relationships into the database. If Neo4j is offline or not configured, it gracefully degrades to serve the graph data entirely from server memory.

### 3. The API Server (`src/server.js`)
An Express server that glues the application together. It acts as a middleman between the frontend UI and the backend data, exposing key endpoints:
- `POST /api/analyze`: Triggers the `analyzer.js` to parse a specific codebase path and store it via `neo4j.js`.
- `GET /api/graph`: Returns the structured graph data (either from Neo4j, memory, or fresh generation) to be rendered.
- `GET /api/node-details`: Fetches metadata and specific code snippets for individual nodes when a user clicks on them.
- `GET /api/health`: Provides diagnostic info regarding database connection and configuration state.

### 4. The Frontend (`public/` directory)
A clean web interface built with standard HTML, CSS (`styles.css`), and JavaScript. It consumes the REST API (`/api/graph`) and renders an interactive, force-directed graph visually illustrating the dependencies. Users can click on individual items on the graph to slide open preview windows indicating how those entities are defined and interconnected (calling `/api/node-details`). 

---

## 🚀 Deployment & Usage
The app is designed to run locally (`npm run dev`) targeting a sample codebase, or deployed to the cloud (e.g., via Railway or Render) utilizing a Neo4j AuraDB instance to persist the graph structure across sessions.
