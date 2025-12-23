from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import Response, JSONResponse
import asyncio, uuid, time

app = FastAPI()

agents = {}              # agent_id -> {"ws": websocket, "last_seen": time}
pending = {}             # request_id -> asyncio.Future
OFFLINE_AFTER = 20       # seconds

@app.get("/")
async def root():
    return {
        "status": "OK",
        "message": "Railway Tunnel Server Running",
        "usage": "/proxy/{agent_id}?url=https://example.com"
    }

@app.get("/agents")
async def list_agents():
    now = time.time()
    out = []
    for aid, a in agents.items():
        out.append({
            "agent_id": aid,
            "status": "online" if now - a["last_seen"] <= OFFLINE_AFTER else "offline",
            "last_seen": a["last_seen"]
        })
    return out

@app.api_route("/proxy/{agent_id}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy(agent_id: str, request: Request):
    if agent_id not in agents:
        return JSONResponse({"error": "Agent offline"}, status_code=404)

    target_url = request.query_params.get("url")
    if not target_url:
        return JSONResponse({"error": "Missing ?url="}, status_code=400)

    req_id = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    pending[req_id] = fut

    body = await request.body()
    payload = {
        "action": "proxy_request",
        "request_id": req_id,
        "method": request.method,
        "url": target_url,
        "headers": dict(request.headers),
        "body": body.decode("utf-8", errors="ignore")
    }

    try:
        await agents[agent_id]["ws"].send_json(payload)
        resp = await asyncio.wait_for(fut, timeout=60)

        return Response(
            content=resp.get("body", b""),
            status_code=resp.get("status", 200),
            headers=resp.get("headers", {})
        )

    except asyncio.TimeoutError:
        return JSONResponse({"error": "Agent timeout"}, status_code=504)
    finally:
        pending.pop(req_id, None)

@app.websocket("/ws/{agent_id}")
async def ws_agent(ws: WebSocket, agent_id: str):
    await ws.accept()
    agents[agent_id] = {"ws": ws, "last_seen": time.time()}
    print(f"[CONNECTED] Agent {agent_id}")

    try:
        while True:
            data = await ws.receive_json()
            agents[agent_id]["last_seen"] = time.time()

            if data.get("type") == "proxy_response":
                rid = data.get("request_id")
                if rid in pending:
                    pending[rid].set_result(data)

    except WebSocketDisconnect:
        print(f"[DISCONNECTED] Agent {agent_id}")
        agents.pop(agent_id, None)
