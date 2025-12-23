from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio, time, uuid

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =======================
# STORAGE
# =======================
agents = {}          # agent_id -> info
ws_agents = {}       # agent_id -> websocket

# =======================
# BASIC STATUS
# =======================
@app.get("/")
async def status():
    return {
        "status": "Online",
        "agents": len(agents)
    }

# =======================
# REGISTER AGENT
# =======================
@app.post("/agent/register")
async def register_agent(data: dict):
    agent_id = data["agent_id"]
    agents[agent_id] = {
        "agent_id": agent_id,
        "ip": data.get("ip"),
        "city": data.get("city"),
        "country": data.get("country"),
        "type": data.get("type", "HTTP/HTTPS"),
        "status": "online",
        "latency": None,
        "last_seen": time.time()
    }
    return {"ok": True}

# =======================
# HEARTBEAT
# =======================
@app.post("/agent/heartbeat")
async def heartbeat(data: dict):
    agent_id = data["agent_id"]
    if agent_id in agents:
        agents[agent_id]["last_seen"] = time.time()
        agents[agent_id]["status"] = "online"
    return {"ok": True}

# =======================
# LIST AGENTS (DASHBOARD)
# =======================
@app.get("/agents")
async def list_agents():
    return list(agents.values())

# =======================
# WEBSOCKET (COMMAND CHANNEL)
# =======================
@app.websocket("/ws/{agent_id}")
async def ws_agent(websocket: WebSocket, agent_id: str):
    await websocket.accept()
    ws_agents[agent_id] = websocket
    print(f"[WS] Agent connected: {agent_id}")

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_agents.pop(agent_id, None)
        if agent_id in agents:
            agents[agent_id]["status"] = "offline"
        print(f"[WS] Agent disconnected: {agent_id}")

# =======================
# CLEANUP OFFLINE AGENTS
# =======================
@app.on_event("startup")
async def cleanup_loop():
    async def loop():
        while True:
            now = time.time()
            for a in agents.values():
                if now - a["last_seen"] > 15:
                    a["status"] = "offline"
            await asyncio.sleep(5)
    asyncio.create_task(loop())
