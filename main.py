from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Response
import asyncio
import base64
import uuid

app = FastAPI()
agents = {}

@app.get("/")
async def status():
    return {"status": "Server is running", "agent_connected": "main" in agents}

@app.websocket("/ws/oran_pc")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    agents["main"] = websocket
    print("Agent connected")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if "main" in agents:
            del agents["main"]

@app.api_route("/proxy", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_handler(request: Request, target_url: str):
    if "main" not in agents:
        return Response("Error: Agent offline", status_code=503)

    ws = agents["main"]
    task_id = str(uuid.uuid4())
    body = await request.body()
    
    await ws.send_json({
        "task_id": task_id,
        "url": target_url,
        "method": request.method,
        "body": base64.b64encode(body).decode('utf-8'),
        "headers": dict(request.headers)
    })

    try:
        response_data = await asyncio.wait_for(ws.receive_json(), timeout=25)
        content = base64.b64decode(response_data["content"])
        return Response(content=content, status_code=response_data["status"], headers=response_data.get("headers", {}))
    except Exception:
        return Response("Timeout: No response from agent", status_code=504)
