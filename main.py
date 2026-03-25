"""
Agent Registry - A DNS-like directory for AI agents.
"""

import sqlite3
import secrets
from datetime import datetime, timezone
from typing import Optional
from contextlib import contextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

# ─────────────────────────────────────────────
# App
# ─────────────────────────────────────────────

app = FastAPI(
    title="Agent Registry",
    description="""
## Agent Registry

A lightweight DNS-like directory for AI agents.

Anyone can register, update, or remove agents — no authentication required.
This is an open phonebook. Security can be layered on later.

### Quick Start
1. `POST /agents/register` — register your agent, get back your `id`
2. `GET /agents/search?q=your-topic` — find agents by keyword or capability
3. `PUT /agents/{id}` — update your record anytime
4. `DELETE /agents/{id}` — remove yourself

### Agent Card (A2A compatible)
Each agent gets a card at `/.well-known/agent/{id}` following the Agent2Agent standard.
""",
    version="0.1.0",
)

DB_PATH = "agent-registry.db"

# ─────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id            TEXT PRIMARY KEY,
                name          TEXT NOT NULL,
                description   TEXT,
                owner         TEXT,
                endpoint      TEXT NOT NULL,
                capabilities  TEXT,
                tags          TEXT,
                protocol      TEXT DEFAULT 'a2a',
                status        TEXT DEFAULT 'online',
                registered_at TEXT NOT NULL,
                updated_at    TEXT NOT NULL
            )
        """)
        conn.commit()

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def row_to_dict(row) -> dict:
    d = dict(row)
    d["capabilities"] = [c.strip() for c in (d.get("capabilities") or "").split(",") if c.strip()]
    d["tags"] = [t.strip() for t in (d.get("tags") or "").split(",") if t.strip()]
    return d

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def get_agent_or_404(conn, agent_id: str):
    row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")
    return row

# ─────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────

class AgentRegister(BaseModel):
    name: str
    description: Optional[str] = None
    owner: Optional[str] = None
    endpoint: str
    capabilities: Optional[list[str]] = []
    tags: Optional[list[str]] = []
    protocol: Optional[str] = "a2a"
    status: Optional[str] = "online"

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    owner: Optional[str] = None
    endpoint: Optional[str] = None
    capabilities: Optional[list[str]] = None
    tags: Optional[list[str]] = None
    protocol: Optional[str] = None
    status: Optional[str] = None

# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

@app.on_event("startup")
def startup():
    init_db()

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")

@app.get("/health", tags=["System"], summary="Health check")
def health():
    return {"status": "ok", "service": "agent-registry", "version": "0.1.0"}

# ── Agent Card (A2A standard) ─────────────────

@app.get("/.well-known/agent/{agent_id}", tags=["Agent Cards"], summary="Get A2A-compatible agent card")
def agent_card(agent_id: str):
    """
    Returns a standard Agent Card for the given agent ID.
    Compatible with Google's Agent2Agent (A2A) protocol.

    Agents can also be discovered at `/.well-known/agent-card.json` for the registry itself.
    """
    with get_db() as conn:
        row = get_agent_or_404(conn, agent_id)
    d = row_to_dict(row)
    return {
        "schema_version": "0.3",
        "name": d["name"],
        "description": d["description"],
        "url": d["endpoint"],
        "capabilities": {
            "skills": [{"id": c, "name": c} for c in d["capabilities"]]
        },
        "tags": d["tags"],
        "protocol": d["protocol"],
        "owner": d["owner"],
        "status": d["status"],
        "registered_at": d["registered_at"],
    }

@app.get("/.well-known/agent-card.json", tags=["Agent Cards"], summary="Agent card for Agent Registry itself")
def registry_agent_card():
    """
    Agent Registry's own agent card — describes the registry as an agent.
    """
    return {
        "schema_version": "0.3",
        "name": "Agent Registry",
        "description": "A DNS-like directory for AI agents. Register, discover, and reach other agents.",
        "url": "http://localhost:8080",
        "capabilities": {
            "skills": [
                {"id": "agent-discovery", "name": "Discover agents by capability or keyword"},
                {"id": "agent-registration", "name": "Register a new agent"},
            ]
        },
        "tags": ["registry", "discovery", "directory"],
        "protocol": "a2a",
    }

# ── Agents CRUD ───────────────────────────────

@app.post("/agents/register", tags=["Agents"], summary="Register a new agent")
def register_agent(agent: AgentRegister):
    """
    Register your agent. Returns an `id` you can use to update or remove your record later.
    No token required — this is an open directory.
    """
    agent_id = secrets.token_urlsafe(12)
    ts = now_iso()

    with get_db() as conn:
        conn.execute("""
            INSERT INTO agents (id, name, description, owner, endpoint, capabilities, tags, protocol, status, registered_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            agent_id,
            agent.name,
            agent.description,
            agent.owner,
            agent.endpoint,
            ",".join(agent.capabilities or []),
            ",".join(agent.tags or []),
            agent.protocol,
            agent.status,
            ts,
            ts,
        ))
        conn.commit()
        row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()

    return row_to_dict(row)

@app.get("/agents", tags=["Agents"], summary="List all agents")
def list_agents(status: Optional[str] = Query(None, description="Filter by status: online, offline")):
    """List all registered agents."""
    with get_db() as conn:
        if status:
            rows = conn.execute("SELECT * FROM agents WHERE status = ? ORDER BY registered_at DESC", (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM agents ORDER BY registered_at DESC").fetchall()
    return {"count": len(rows), "agents": [row_to_dict(r) for r in rows]}

@app.get("/agents/search", tags=["Agents"], summary="Search agents by keyword or capability")
def search_agents(
    q: Optional[str] = Query(None, description="Keyword search across name, description, capabilities, tags"),
    cap: Optional[str] = Query(None, description="Exact capability match (e.g. 'led-diagnostics')"),
    tag: Optional[str] = Query(None, description="Exact tag match (e.g. 'hardware')"),
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """
    Search the registry.

    - `?q=LED` — full-text keyword search
    - `?cap=firmware-analysis` — find by capability
    - `?tag=hardware` — find by tag
    - Combine any filters
    """
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM agents ORDER BY registered_at DESC").fetchall()

    results = [row_to_dict(r) for r in rows]

    if q:
        ql = q.lower()
        results = [
            r for r in results
            if ql in (r.get("name") or "").lower()
            or ql in (r.get("description") or "").lower()
            or any(ql in c.lower() for c in r.get("capabilities", []))
            or any(ql in t.lower() for t in r.get("tags", []))
        ]
    if cap:
        results = [r for r in results if cap.lower() in [c.lower() for c in r.get("capabilities", [])]]
    if tag:
        results = [r for r in results if tag.lower() in [t.lower() for t in r.get("tags", [])]]
    if status:
        results = [r for r in results if r.get("status") == status]

    return {"count": len(results), "results": results}

@app.get("/agents/{agent_id}", tags=["Agents"], summary="Get a single agent")
def get_agent(agent_id: str):
    with get_db() as conn:
        row = get_agent_or_404(conn, agent_id)
    return row_to_dict(row)

@app.put("/agents/{agent_id}", tags=["Agents"], summary="Update an agent record")
def update_agent(agent_id: str, update: AgentUpdate):
    """Update any field on an agent record. No token required."""
    with get_db() as conn:
        row = get_agent_or_404(conn, agent_id)
        current = row_to_dict(row)

        fields = {
            "name":         update.name         if update.name         is not None else current["name"],
            "description":  update.description  if update.description  is not None else current["description"],
            "owner":        update.owner         if update.owner        is not None else current["owner"],
            "endpoint":     update.endpoint      if update.endpoint     is not None else current["endpoint"],
            "capabilities": ",".join(update.capabilities) if update.capabilities is not None else ",".join(current["capabilities"]),
            "tags":         ",".join(update.tags)         if update.tags         is not None else ",".join(current["tags"]),
            "protocol":     update.protocol      if update.protocol     is not None else current["protocol"],
            "status":       update.status        if update.status       is not None else current["status"],
            "updated_at":   now_iso(),
        }

        conn.execute("""
            UPDATE agents SET name=?, description=?, owner=?, endpoint=?, capabilities=?, tags=?, protocol=?, status=?, updated_at=?
            WHERE id=?
        """, (*fields.values(), agent_id))
        conn.commit()
        row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()

    return row_to_dict(row)

@app.delete("/agents/{agent_id}", tags=["Agents"], summary="Remove an agent")
def delete_agent(agent_id: str):
    """Remove an agent from the registry. No token required."""
    with get_db() as conn:
        get_agent_or_404(conn, agent_id)
        conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
        conn.commit()
    return {"message": f"Agent {agent_id} removed"}
