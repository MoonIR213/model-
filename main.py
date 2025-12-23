from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse, Response
import asyncio, uuid, time

app = FastAPI()

agents = {}
pending = {}
OFFLINE_AFTER = 20

@app.get("/")
async def health():
    return {"status": "OK", "message": "Railway Tunnel Server Running"}

@app.websocket("/ws/{agent_id}")
async def ws_agent(ws: WebSocket, agent_id: str):
    await ws.accept()
    agents[agent_id] = {"ws": ws, "last_seen": time.time()}
    print("[CONNECTED]", agent_id)

    try:
        while True:
            data = await ws.receive_json()
            agents[agent_id]["last_seen"] = time.time()

            if data.get("type") == "proxy_response":
                rid = data["request_id"]
                if rid in pending:
                    pending[rid].set_result(data)

    except WebSocketDisconnect:
        agents.pop(agent_id, None)
        print("[DISCONNECTED]", agent_id)

@app.api_route("/proxy/{agent_id}", methods=["GET","POST","PUT","DELETE","PATCH"])
async def proxy(agent_id: str, request: Request):
    if agent_id not in agents:
        return JSONResponse({"error": "Agent offline"}, 404)

    url = request.query_params.get("url")
    if not url:
        return JSONResponse({"error": "Missing url"}, 400)

    rid = str(uuid.uuid4())
    fut = asyncio.get_running_loop().create_future()
    pending[rid] = fut

    body = await request.body()

    await agents[agent_id]["ws"].send_json({
        "type": "proxy_request",
        "request_id": rid,
        "method": request.method,
        "url": url,
        "headers": dict(request.headers),
        "body": body.decode(errors="ignore")
    })

    try:
        resp = await asyncio.wait_for(fut, timeout=60)
        return Response(resp["body"], resp["status"], resp["headers"])
    except asyncio.TimeoutError:
        return JSONResponse({"error": "Timeout"}, 504)
    finally:
        pending.pop(rid, None)
