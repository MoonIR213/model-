from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import time
import asyncio

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===============================
# STORAGE
# ===============================
agents = {}  # agent_id -> data
OFFLINE_AFTER = 10  # seconds

# ===============================
# API
# ===============================
@app.get("/")
async def root():
    return {
        "status": "OK",
        "message": "Agent Proxy Monitor Running",
        "agents": "/agents"
    }

@app.get("/agents")
async def get_agents():
    now = time.time()
    result = []

    for agent_id, a in agents.items():
        status = "online" if now - a["last_seen"] < OFFLINE_AFTER else "offline"
        result.append({
            "ip": a["ip"],
            "port": a["port"],
            "type": a["type"],
            "country": a["country"],
            "latency": a["latency"],
            "status": status
        })

    return result

# ===============================
# WEBSOCKET (AGENT)
# ===============================
@app.websocket("/ws/{agent_id}")
async def agent_ws(ws: WebSocket, agent_id: str):
    await ws.accept()
    print(f"[+] Agent connected: {agent_id}")

    try:
        while True:
            data = await ws.receive_json()

            agents[agent_id] = {
                "ip": data.get("ip"),
                "port": data.get("port"),
                "type": data.get("type"),
                "country": data.get("country", "DZ"),
                "latency": data.get("latency", 0),
                "last_seen": time.time(),
            }

    except WebSocketDisconnect:
        print(f"[-] Agent disconnected: {agent_id}")
