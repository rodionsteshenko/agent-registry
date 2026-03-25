# AgentBeacon

A lightweight, DNS-like registry for AI agents.

Agents register themselves, describe their capabilities, and discover each other — no central orchestrator, no auth system. Just an open phonebook for the agent network.

Compatible with Google's [Agent2Agent (A2A)](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/) protocol via standard Agent Cards.

---

## Quickstart

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn main:app --host 0.0.0.0 --port 8080

# Interactive API docs
open http://localhost:8080/docs
```

---

## API

### Register an agent
```bash
curl -X POST http://localhost:8080/agents/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "led-switch-expert",
    "description": "Knows everything about LED switch firmware and diagnostics",
    "owner": "rodion@nvidia.com",
    "endpoint": "https://my-agent.internal:9000",
    "capabilities": ["led-diagnostics", "firmware-analysis", "switch-config"],
    "tags": ["hardware", "nvidia"],
    "protocol": "a2a"
  }'
```

Returns the full agent record including its `id`. Save the `id` to update or remove yourself later.

### List all agents
```bash
curl http://localhost:8080/agents
curl http://localhost:8080/agents?status=online
```

### Search by keyword, capability, or tag
```bash
curl "http://localhost:8080/agents/search?q=LED"
curl "http://localhost:8080/agents/search?cap=firmware-analysis"
curl "http://localhost:8080/agents/search?tag=hardware"
```

### Update an agent
```bash
curl -X PUT http://localhost:8080/agents/{id} \
  -H "Content-Type: application/json" \
  -d '{"status": "offline"}'
```

### Remove an agent
```bash
curl -X DELETE http://localhost:8080/agents/{id}
```

---

## Agent Cards (A2A)

Every agent gets a standard A2A-compatible card:

```
GET /.well-known/agent/{id}
```

The registry itself is also discoverable:

```
GET /.well-known/agent-card.json
```

---

## Agent Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Auto-generated unique ID |
| `name` | string | Agent name (required) |
| `description` | string | What this agent does |
| `owner` | string | Who owns it (email, name, etc.) |
| `endpoint` | string | URL to reach the agent (required) |
| `capabilities` | list | What the agent can do |
| `tags` | list | Free-form labels |
| `protocol` | string | Communication protocol (default: `a2a`) |
| `status` | string | `online` or `offline` |
| `registered_at` | ISO timestamp | When it was registered |
| `updated_at` | ISO timestamp | Last updated |

---

## Design Philosophy

- **Open by default.** No auth, no accounts. Anyone can read or write. Security can be layered on later.
- **Capability-first discovery.** Search by what an agent *can do*, not just its name.
- **A2A compatible.** Agent Cards follow the emerging Google A2A standard so this registry can federate with the broader ecosystem.
- **Simple to deploy.** One Python file, one SQLite database, two dependencies.

---

## Roadmap

- [ ] Optional `X-Edit-Token` auth (opt-in per agent)
- [ ] Heartbeat / liveness pings (auto-mark agents offline)
- [ ] Semantic search (embeddings-based capability matching)
- [ ] Federation with NANDA / external registries
- [ ] Postgres backend option
- [ ] Agent-to-agent messaging relay

---

## Deploy

```bash
# On any Linux VM
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8080

# With a process manager
nohup uvicorn main:app --host 0.0.0.0 --port 8080 > agentbeacon.log 2>&1 &
```
