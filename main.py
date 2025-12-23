from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import Response, JSONResponse
import asyncio, uuid, time

app = FastAPI()

# =========================
# Storage
# =========================
agents = {}              # agent_id -> {"ws": WebSocket, "last_seen": float}
pending = {}             # request_id -> asyncio.Future

OFFLINE_AFTER = 20  # seconds

# =========================
# Root (health)
# =========================
@app.get("/")
async def root():
    return {
        "status": "OK",
        "message": "Railway Tunnel Server Running",
        "usage": "/proxy/{agent_id}/https://example.com"
    }

# =========================
# List agents
# =========================
@app.get("/agents")
async def list_agents():
    out = []
    now = time.time()
    for aid, data in agents.items():
        out.append({
            "agent_id": aid,
            "status": "online" if now - data["last_seen"] < OFFLINE_AFTER else "offline",
            "last_seen": data["last_seen"]
        })
    return out

# =========================
# PROXY TUNNEL
# =========================
@app.api_route("/proxy/{agent_id}/{target_url:path}",
               methods=["GET","POST","PUT","DELETE","PATCH","OPTIONS","HEAD"])
async def proxy(agent_id: str, target_url: str, request: Request):
    if agent_id not in agents:
        return JSONResponse({"error": "Agent offline/not found"}, status_code=404)

    req_id = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    pending[req_id] = fut

    body = await request.body()
    payload = {
        "type": "proxy_request",
        "request_id": req_id,
        "method": request.method,
        "url": target_url,
        "headers": dict(request.headers),
        "body": body.decode("utf-8", errors="ignore") if body else None
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
        return JSONResponse({"error": "Timeout from agent"}, status_code=504)
    finally:
        pending.pop(req_id, None)

# =========================
# WEBSOCKET (Agent)
# =========================
@app.websocket("/ws/{agent_id}")
async def ws_agent(ws: WebSocket, agent_id: str):
    await ws.accept()
    agents[agent_id] = {"ws": ws, "last_seen": time.time()}
    print(f"[+] Agent connected: {agent_id}")

    try:
        while True:
            msg = await ws.receive_json()
            agents[agent_id]["last_seen"] = time.time()

            if msg.get("type") == "proxy_response":
                rid = msg.get("request_id")
                if rid in pending and not pending[rid].done():
                    pending[rid].set_result(msg)

    except WebSocketDisconnect:
        print(f"[-] Agent disconnected: {agent_id}")
        agents.pop(agent_id, None)

# =========================
# Offline cleanup
# =========================
@app.on_event("startup")
async def cleanup():
    async def loop():
        while True:
            now = time.time()
            for aid in list(agents.keys()):
                if now - agents[aid]["last_seen"] > OFFLINE_AFTER:
                    agents.pop(aid, None)
            await asyncio.sleep(5)
    asyncio.create_task(loop())
