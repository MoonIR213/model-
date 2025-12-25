from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import time, json, os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

app = FastAPI()

templates = Jinja2Templates(directory=TEMPLATE_DIR)

# =========================
# STORAGE
# =========================
agents = {}
agent_info = {}

# =========================
# ROOT
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
    out = []

    for aid, info in agent_info.items():
        out.append({
            "id": aid,
            "status": "online" if now - info["last_seen"] < 15 else "offline",
            "ip": info["ip"],
            "city": info.get("city", "Unknown"),
            "last_seen": int(now - info["last_seen"])
        })

    return out

# =========================
# DASHBOARD (SAFE)
# =========================
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    try:
        now = time.time()
        view = {}

        for aid, info in agent_info.items():
            view[aid] = {
                "ip": info["ip"],
                "city": info.get("city", "Unknown"),
                "status": "online" if now - info["last_seen"] < 15 else "offline",
                "last_seen": int(now - info["last_seen"])
            }

        return templates.TemplateResponse(
            "dashboard.html",
            {"request": request, "agents": view}
        )

    except Exception as e:
        # 🔥 يمنع 500
        return HTMLResponse(
            f"<h2>Dashboard Error</h2><pre>{str(e)}</pre>",
            status_code=200
        )

# =========================
# WEBSOCKET
# =========================
@app.websocket("/ws/agent/{agent_id}")
async def ws_agent(ws: WebSocket, agent_id: str):
    await ws.accept()
    ip = ws.client.host

    agents[agent_id] = ws
    agent_info[agent_id] = {
        "ip": ip,
        "city": "Unknown",
        "last_seen": time.time()
    }

    print(f"[AGENT] {agent_id} connected from {ip}")

    try:
        while True:
            msg = await ws.receive_text()
            data = json.loads(msg)

            agent_info[agent_id]["last_seen"] = time.time()

            if data.get("type") == "ping":
                await ws.send_text(json.dumps({
                    "type": "pong",
                    "timestamp": time.time()
                }))

    except WebSocketDisconnect:
        print(f"[AGENT] {agent_id} disconnected")

    finally:
        agents.pop(agent_id, None)
        agent_info.pop(agent_id, None)
