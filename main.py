import uuid
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# agent_id -> info
agents = {}
# conn_id -> (client_ws, agent_ws)
connections = {}

OFFLINE_AFTER = 15  # seconds


@app.get("/")
async def root():
    return {"status": "OK"}


# =========================
# API: LIST AGENTS
# =========================
@app.get("/api/agents")
async def api_agents():
    now = time.time()
    data = []

    for aid, info in agents.items():
        status = "online" if now - info["last_seen"] < OFFLINE_AFTER else "offline"
        data.append({
            "agent_id": aid,
            "status": status,
            "ip": info["ip"],
            "city": info["city"],
            "last_seen": int(now - info["last_seen"]),
        })

    return data


# =========================
# AGENT CONNECT
# =========================
@app.websocket("/ws/agent/{agent_id}")
async def agent_ws(ws: WebSocket, agent_id: str):
    await ws.accept()

    client_ip = ws.client.host

    # مدينة افتراضية (نغيرها لاحقًا)
    city = "Unknown"
    if "ANNABA" in agent_id.upper():
        city = "Annaba"
    elif "ORAN" in agent_id.upper():
        city = "Oran"

    agents[agent_id] = {
        "ws": ws,
        "ip": client_ip,
        "city": city,
        "last_seen": time.time(),
    }

    print(f"[AGENT] {agent_id} connected from {client_ip}")

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
# CLIENT CONNECT
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
