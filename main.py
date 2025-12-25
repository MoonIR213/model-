import asyncio
import struct
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

# تخزين الوكلاء والروابط
agents = {}        # agent_id -> WebSocket
client_links = {}  # client_ws -> (agent_ws, client_id_bytes)

@app.get("/")
async def root():
    return {"status": "Relay Server Online", "version": "2.0-Binary"}

@app.websocket("/ws/agent/{agent_id}")
async def ws_agent(ws: WebSocket, agent_id: str):
    await ws.accept()
    agents[agent_id] = ws
    print(f"[AGENT] {agent_id} متصل الآن.")
    try:
        while True:
            # استقبال بيانات ثنائية من الوكيل
            data = await ws.receive_bytes()
            if len(data) > 16:
                target_client_id = data[:16] # أول 16 بايت هي معرف العميل
                # توجيه البيانات للعميل الصحيح فقط
                for c_ws, (a_ws, c_id) in list(client_links.items()):
                    if a_ws == ws and c_id == target_client_id:
                        await c_ws.send_bytes(data[16:])
    except WebSocketDisconnect:
        print(f"[AGENT] {agent_id} انقطع الاتصال.")
    finally:
        agents.pop(agent_id, None)

@app.websocket("/ws/client/{agent_id}")
async def ws_client(ws: WebSocket, agent_id: str):
    await ws.accept()
    agent_ws = agents.get(agent_id)
    if not agent_ws:
        await ws.close(code=1000)
        return

    import os
    client_id = os.urandom(16) # توليد معرف فريد لمنع التداخل
    client_links[ws] = (agent_ws, client_id)
    
    try:
        while True:
            payload = await ws.receive_bytes()
            # دمج المعرف مع البيانات وإرسالها للوكيل
            await agent_ws.send_bytes(client_id + payload)
    except WebSocketDisconnect:
        pass
    finally:
        client_links.pop(ws, None)
