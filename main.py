# server_tcp_relay.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio, json, base64, uuid

app = FastAPI()

agents = {}
sessions = {}

@app.websocket("/ws/{agent_id}")
async def ws_agent(ws: WebSocket, agent_id: str):
    await ws.accept()
    agents[agent_id] = ws
    try:
        while True:
            msg = await ws.receive_text()
            data = json.loads(msg)

            sid = sessions.get("current")
            if sid:
                client_ws = sessions[sid]["client"]
                await client_ws.send_text(msg)

    except WebSocketDisconnect:
        agents.pop(agent_id, None)

@app.websocket("/tcp/{agent_id}")
async def tcp_client(ws: WebSocket, agent_id: str):
    await ws.accept()

    if agent_id not in agents:
        await ws.close()
        return

    agent_ws = agents[agent_id]
    session_id = str(uuid.uuid4())

    sessions["current"] = {
        "client": ws,
        "agent": agent_ws
    }

    try:
        # أول رسالة من العميل تحدد الهدف
        first = json.loads(await ws.receive_text())
        await agent_ws.send_text(json.dumps({
            "type": "tcp_open",
            "host": first["host"],
            "port": first["port"]
        }))

        while True:
            msg = await ws.receive_text()
            await agent_ws.send_text(msg)

    except WebSocketDisconnect:
        await agent_ws.send_text(json.dumps({"type": "tcp_close"}))
        sessions.pop("current", None)
