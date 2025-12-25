from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import time

app = FastAPI()

templates = Jinja2Templates(directory="model/templates")

# =========================
# AGENTS STATE
# =========================
agents = {}        # agent_id -> websocket
agent_info = {}   # agent_id -> info dict


# =========================
# UI ROUTES
# =========================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# =========================
# API
# =========================
@app.get("/api/agents")
async def api_agents():
    now = time.time()
    result = []

    for aid, info in agent_info.items():
        status = "online" if now - info["last_seen"] < 15 else "offline"
        result.append({
            "agent_id": aid,
            "status": status,
            "ip": info["ip"],
            "city": info.get("city", "Unknown")
        })

    return result


# =========================
# WEBSOCKET (CRITICAL)
# =========================
@app.websocket("/ws/agent/{agent_id}")
async def ws_agent(websocket: WebSocket, agent_id: str):
    await websocket.accept()

    ip = websocket.client.host
    print(f"[AGENT] {agent_id} connected from {ip}")

    agents[agent_id] = websocket
    agent_info[agent_id] = {
        "ip": ip,
        "city": "Unknown",
        "last_seen": time.time()
    }

    try:
        while True:
            data = await websocket.receive_bytes()
            agent_info[agent_id]["last_seen"] = time.time()

    except WebSocketDisconnect:
        print(f"[AGENT] {agent_id} disconnected")

    finally:
        agents.pop(agent_id, None)
        agent_info.pop(agent_id, None)
