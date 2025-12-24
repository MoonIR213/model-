# server_tcp_relay_fixed.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json, uuid

app = FastAPI()

agents = {}
clients = {}  # sid -> client_ws

@app.websocket("/ws/{agent_id}")
async def ws_agent(ws: WebSocket, agent_id: str):
    await ws.accept()
    agents[agent_id] = ws
    try:
        while True:
            msg = await ws.receive_text()
            data = json.loads(msg)

            sid = data.get("sid")
            if sid and sid in clients:
                await clients[sid].send_text(msg)

    except WebSocketDisconnect:
        agents.pop(agent_id, None)

@app.websocket("/tcp/{agent_id}")
async def tcp_client(ws: WebSocket, agent_id: str):
    await ws.accept()

    if agent_id not in agents:
        await ws.close()
        return

    agent_ws = agents[agent_id]
    sid = str(uuid.uuid4())
    clients[sid] = ws

    try:
        first = json.loads(await ws.receive_text())

        await agent_ws.send_text(json.dumps({
            "type": "tcp_open",
            "sid": sid,
            "host": first["host"],
            "port": first["port"]
        }))

        while True:
            msg = await ws.receive_text()
            data = json.loads(msg)
            data["sid"] = sid
            await agent_ws.send_text(json.dumps(data))

    except WebSocketDisconnect:
        await agent_ws.send_text(json.dumps({
            "type": "tcp_close",
            "sid": sid
        }))
        clients.pop(sid, None)
