import uuid
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# =========================
# APP
# =========================
app = FastAPI()

templates = Jinja2Templates(directory="templates")

# agent_id -> info
agents = {}

# conn_id -> (client_ws, agent_ws)
connections = {}

OFFLINE_AFTER = 15  # seconds


# =========================
# ROOT
# =========================
@app.get("/")
async def root():
    return {"status": "OK"}


# =========================
# DASHBOARD (UI)
# =========================
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(
        "index.html",   # ✅ الملف الموجود فعليًا
        {"request": request}
    )


# =========================
# API: AGENTS LIST
# =========================
@app.get("/api/agents")
async def api_agents():
    now = time.time()
    result = []

    for agent_id, info in agents.items():
        status = "online" if now - info["last_seen"] < OFFLINE_AFTER else "offline"

        result.append({
            "agent_id": agent_id,
            "status": status,
            "ip": info["ip"],
            "city": info["city"],
        })

    return result


# =========================
# AGENT WEBSOCKET
# =========================
@app.websocket("/ws/agent/{agent_id}")
async def agent_ws(ws: WebSocket, agent_id: str):
    await ws.accept()

    ip = ws.client.host

    # City detection (simple)
    city = "Unknown"
    aid = agent_id.upper()
    if "ANNABA" in aid:
        city = "Annaba"
    elif "ORAN" in aid:
        city = "Oran"
    elif "ALGIERS" in aid:
        city = "Algiers"

    agents[agent_id] = {
        "ws": ws,
        "ip": ip,
        "city": city,
        "last_seen": time.time(),
    }

    print(f"[AGENT] {agent_id} connected from {ip}")

    try:
        while True:
            msg = await ws.receive_bytes()
            agents[agent_id]["last_seen"] = time.time()

            conn_id = msg[:36].decode(errors="ignore")
            payload = msg[36:]

            if conn_id in connections:
                client_ws, _ = connections[conn_id]
                await client_ws.send_bytes(payload)

    except WebSocketDisconnect:
        pass
    finally:
        agents.pop(agent_id, None)
        print(f"[AGENT] {agent_id} disconnected")


# =========================
# CLIENT WEBSOCKET
# =========================
@app.websocket("/ws/client/{agent_id}")
async def client_ws(ws: WebSocket, agent_id: str):
    await ws.accept()

    if agent_id not in agents:
        await ws.close()
        return

    agent_ws = agents[agent_id]["ws"]
    conn_id = str(uuid.uuid4())
    connections[conn_id] = (ws, agent_ws)

    print(f"[CLIENT] New connection {conn_id} via {agent_id}")

    try:
        while True:
            data = await ws.receive_bytes()
            await agent_ws.send_bytes(conn_id.encode() + data)

    except WebSocketDisconnect:
        pass
    finally:
        connections.pop(conn_id, None)
        print(f"[CLIENT] Closed {conn_id}")
