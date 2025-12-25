from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import time

app = FastAPI()

templates = Jinja2Templates(directory="model/templates")

# =========================
# STORAGE
# =========================
agents = {}        # agent_id -> websocket
agent_info = {}   # agent_id -> info dict


# =========================
# HEALTH CHECK
# =========================
@app.get("/")
async def root():
    return {"status": "OK"}


# =========================
# API
# =========================
@app.get("/api/agents")
async def api_agents():
    now = time.time()
    data = []

    for agent_id, info in agent_info.items():
        status = "online" if now - info["last_seen"] < 15 else "offline"
        data.append({
            "id": agent_id,
            "status": status,
            "ip": info.get("ip"),
            "city": info.get("city", "Unknown")
        })

    return data


# =========================
# DASHBOARD
# =========================
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "agents": agent_info
    })


# =========================
# WEBSOCKET (THE MISSING PIECE)
# =========================
@app.websocket("/ws/agent/{agent_id}")
async def ws_agent(websocket: WebSocket, agent_id: str):
    await websocket.accept()

    client_ip = websocket.client.host

    agents[agent_id] = websocket
    agent_info[agent_id] = {
        "ip": client_ip,
        "city": "Unknown",
        "last_seen": time.time()
    }

    print(f"[AGENT] {agent_id} connected from {client_ip}")

    try:
        while True:
            msg = await websocket.receive_bytes()
            agent_info[agent_id]["last_seen"] = time.time()

    except WebSocketDisconnect:
        print(f"[AGENT] {agent_id} disconnected")

    finally:
        agents.pop(agent_id, None)
        agent_info.pop(agent_id, None)
