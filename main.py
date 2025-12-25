import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

agents = {}        # agent_id -> websocket
connections = {}  # conn_id -> (client_ws, agent_ws)


@app.get("/")
async def root():
    return {"status": "OK"}


# =========================
# AGENT CONNECT
# =========================
@app.websocket("/ws/agent/{agent_id}")
async def agent_ws(ws: WebSocket, agent_id: str):
    await ws.accept()
    agents[agent_id] = ws
    print(f"[AGENT] {agent_id} connected")

    try:
        while True:
            msg = await ws.receive_bytes()
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

    agent_ws = agents[agent_id]
    conn_id = str(uuid.uuid4())
    connections[conn_id] = (ws, agent_ws)

    print(f"[CLIENT] new conn {conn_id} via agent {agent_id}")

    try:
        while True:
            data = await ws.receive_bytes()
            await agent_ws.send_bytes(conn_id.encode() + data)

    except WebSocketDisconnect:
        pass
    finally:
        connections.pop(conn_id, None)
        print(f"[CLIENT] closed {conn_id}")
