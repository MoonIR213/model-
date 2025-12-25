from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import time

app = FastAPI()
templates = Jinja2Templates(directory="model/templates")

# agent_id -> info
agents = {}

# ======================
# HTTP
# ======================
@app.get("/")
async def root():
    return {"status": "OK"}

@app.get("/api/agents")
async def api_agents():
    now = time.time()
    data = []
    for aid, info in agents.items():
        status = "online" if now - info["last_seen"] < 10 else "offline"
        data.append({
            "agent_id": aid,
            "status": status,
            "ip": info["ip"],
            "city": info.get("city", "Unknown")
        })
    return data

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "agents": await api_agents()}
    )

# ======================
# WEBSOCKET (AGENT)
# ======================
@app.websocket("/ws/agent/{agent_id}")
async def ws_agent(ws: WebSocket, agent_id: str):
    await ws.accept()

    client = ws.client
    ip = client.host if client else "unknown"

    agents[agent_id] = {
        "ip": ip,
        "city": "Unknown",
        "last_seen": time.time()
    }

    print(f"[AGENT] {agent_id} connected from {ip}")

    try:
        while True:
            await ws.receive_bytes()
            agents[agent_id]["last_seen"] = time.time()

    except WebSocketDisconnect:
        print(f"[AGENT] {agent_id} disconnected")

    finally:
        agents.pop(agent_id, None)
