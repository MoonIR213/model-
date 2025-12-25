import uuid
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()

templates = Jinja2Templates(directory="templates")

agents = {}
connections = {}
OFFLINE_AFTER = 15


@app.get("/")
async def root():
    return {"status": "OK"}


# =========================
# DASHBOARD PAGE
# =========================
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request}
    )


# =========================
# API: AGENTS LIST
# =========================
@app.get("/api/agents")
async def api_agents():
    now = time.time()
    out = []

    for aid, info in agents.items():
        status = "online" if now - info["last_seen"] < OFFLINE_AFTER else "offline"
        out.append({
            "agent_id": aid,
            "status": status,
            "ip": info["ip"],
            "city": info["city"],
        })

    return out


# =========================
# AGENT WS
# =========================
@app.websocket("/ws/agent/{agent_id}")
async def agent_ws(ws: WebSocket, agent_id: str):
    await ws.accept()

    ip = ws.client.host
    city = "Unknown"
    if "ANNABA" in agent_id.upper():
        city = "Annaba"
    elif "ORAN" in agent_id.upper():
        city = "Oran"

    agents[agent_id] = {
        "ws": ws,
        "ip": ip,
        "city": city,
        "last_seen": time.time(),
    }

    print(f"[AGENT] {agent_id} connected")

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
# CLIENT WS
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

    try:
        while True:
            data = await ws.receive_bytes()
            await agent_ws.send_bytes(conn_id.encode() + data)
    except WebSocketDisconnect:
        pass
    finally:
        connections.pop(conn_id, None)
