from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import Response, JSONResponse
import asyncio, uuid, base64, time

app = FastAPI()

agents = {}        # agent_id -> websocket
pending = {}       # request_id -> Future

# =========================
# PROXY VIA LINK
# =========================
@app.api_route(
    "/proxy/{agent_id}/{target:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"]
)
async def proxy(agent_id: str, target: str, request: Request):
    if agent_id not in agents:
        return JSONResponse({"error": "Agent offline"}, status_code=404)

    request_id = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    pending[request_id] = fut

    body = await request.body()

    payload = {
        "type": "http_request",
        "request_id": request_id,
        "method": request.method,
        "url": target,
        "headers": dict(request.headers),
        "body_base64": base64.b64encode(body).decode() if body else None
    }

    try:
        await agents[agent_id].send_json(payload)
        resp = await asyncio.wait_for(fut, timeout=30)

        content = base64.b64decode(resp.get("body_base64", "")) \
                  if resp.get("body_base64") else b""

        return Response(
            content=content,
            status_code=resp.get("status", 200),
            headers=resp.get("headers", {})
        )

    except asyncio.TimeoutError:
        return JSONResponse({"error": "Agent timeout"}, status_code=504)

    finally:
        pending.pop(request_id, None)

# =========================
# WEBSOCKET
# =========================
@app.websocket("/ws/{agent_id}")
async def ws(websocket: WebSocket, agent_id: str):
    await websocket.accept()
    agents[agent_id] = websocket
    print(f"[+] Agent connected: {agent_id}")

    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "http_response":
                rid = data.get("request_id")
                if rid in pending and not pending[rid].done():
                    pending[rid].set_result(data)

    except WebSocketDisconnect:
        agents.pop(agent_id, None)
        print(f"[-] Agent disconnected: {agent_id}")

if __name__ == "__main__":
    import uvicorn, os
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
