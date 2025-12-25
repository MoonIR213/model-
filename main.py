# server.py
from fastapi import FastAPI, WebSocket
import json

app = FastAPI()
agents = {}

@app.websocket("/ws/agent/{agent_id}")
async def agent_ws(ws: WebSocket, agent_id: str):
    await ws.accept()
    agents[agent_id] = ws
    print("Agent connected:", agent_id)

    try:
        while True:
            msg = await ws.receive_text()
            await ws.send_text(msg)
    except:
        pass
    finally:
        agents.pop(agent_id, None)


@app.websocket("/ws/client/{agent_id}")
async def client_ws(ws: WebSocket, agent_id: str):
    await ws.accept()
    agent = agents.get(agent_id)

    if not agent:
        await ws.close()
        return

    async def forward(src, dst):
        while True:
            data = await src.receive_text()
            await dst.send_text(data)

    await asyncio.gather(
        forward(ws, agent),
        forward(agent, ws)
    )
