from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import asyncio, time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

# ======================
# Storage
# ======================
agents = {}  # agent_id -> data

OFFLINE_AFTER = 15  # seconds

# ======================
# Web UI
# ======================
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# ======================
# API
# ======================
@app.get("/agents")
async def list_agents():
    return list(agents.values())

@app.get("/status")
async def status():
    return {
        "status": "Online",
        "agents": len(agents)
    }

# ======================
# WebSocket
# ======================
@app.websocket("/ws/{agent_id}")
async def ws_agent(websocket: WebSocket, agent_id: str):
    await websocket.accept()

    agents[agent_id] = {
        "agent_id": agent_id,
        "ip": websocket.client.host,
        "type": "HTTPS",
        "country": "DZ",
        "city": agent_id.replace("_pc", "").upper(),
        "latency": "-",
        "status": "online",
        "last_seen": time.time()
    }

    print(f"[+] Connected {agent_id}")

    try:
        while True:
            await websocket.receive_text()   # heartbeat
            agents[agent_id]["last_seen"] = time.time()
            agents[agent_id]["status"] = "online"
    except WebSocketDisconnect:
        print(f"[-] Disconnected {agent_id}")
        agents[agent_id]["status"] = "offline"

# ======================
# Cleanup Task
# ======================
@app.on_event("startup")
async def cleanup_loop():
    async def loop():
        while True:
            now = time.time()
            for a in agents.values():
                if now - a["last_seen"] > OFFLINE_AFTER:
                    a["status"] = "offline"
            await asyncio.sleep(5)
    asyncio.create_task(loop())
