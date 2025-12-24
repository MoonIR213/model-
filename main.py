# server_tcp_relay_full.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
import json, uuid

app = FastAPI()

# =========================
# Storage
# =========================
agents = {}     # agent_id -> websocket
clients = {}    # session_id -> client websocket


# =========================
# HTTP root (مهم جدًا لـ Railway)
# =========================
@app.get("/")
async def root():
    return PlainTextResponse("OK")


# =========================
# WebSocket: Agent
# =========================
@app.websocket("/ws/{agent_id}")
async def ws_agent(ws: WebSocket, agent_id: str):
    await ws.accept()
    agents[agent_id] = ws
    print(f"[SERVER] Agent connected: {agent_id}")

    try:
        while True:
            msg = await ws.receive_text()
            data = json.loads(msg)

            sid = data.get("sid")
            if sid and sid in clients:
                await clients[sid].send_text(msg)

    except WebSocketDisconnect:
        print(f"[SERVER] Agent disconnected: {agent_id}")
        agents.pop(agent_id, None)


# =========================
# WebSocket: TCP Client
# =========================
@app.websocket("/tcp/{agent_id}")
async def tcp_client(ws: WebSocket, agent_id: str):
    await ws.accept()

    if agent_id not in agents:
        await ws.close()
        return

    agent_ws = agents[agent_id]
    session_id = str(uuid.uuid4())
    clients[session_id] = ws

    print(f"[SERVER] TCP session {session_id} via {agent_id}")

    try:
        # أول رسالة = target
        first = json.loads(await ws.receive_text())

        await agent_ws.send_text(json.dumps({
            "type": "tcp_open",
            "sid": session_id,
            "host": first["host"],
            "port": first["port"]
        }))

        while True:
            msg = await ws.receive_text()
            data = json.loads(msg)
            data["sid"] = session_id
            await agent_ws.send_text(json.dumps(data))

    except WebSocketDisconnect:
        await agent_ws.send_text(json.dumps({
            "type": "tcp_close",
            "sid": session_id
        }))
        clients.pop(session_id, None)
        print(f"[SERVER] TCP session closed {session_id}")
