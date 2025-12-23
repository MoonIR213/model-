from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse, Response, HTMLResponse
from fastapi.templating import Jinja2Templates
import asyncio, uuid, time, os

app = FastAPI()
templates = Jinja2Templates(directory="templates")

agents = {}
pending = {}
OFFLINE_AFTER = 15

# ================= UI =================
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/agents")
async def list_agents():
    now = time.time()
    return [
        {
            "agent_id": aid,
            "status": "online" if now - a["last_seen"] <= OFFLINE_AFTER else "offline",
            "last_seen": int(now - a["last_seen"])
        }
        for aid, a in agents.items()
    ]

# ================= PROXY =================
@app.api_route("/proxy/{agent_id}", methods=["GET","POST","PUT","DELETE","PATCH","OPTIONS"])
async def proxy(agent_id: str, request: Request):
    if agent_id not in agents:
        return JSONResponse({"error": "Agent offline"}, 404)

    url = request.query_params.get("url")
    if not url:
        return JSONResponse({"error": "Missing ?url"}, 400)

    rid = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    fut = loop.create_future()
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

# ================= WEBSOCKET =================
@app.websocket("/ws/{agent_id}")
async def ws_agent(ws: WebSocket, agent_id: str):
    await ws.accept()
    agents[agent_id] = {"ws": ws, "last_seen": time.time()}
    print(f"[CONNECTED] {agent_id}")

    try:
        while True:
            data = await ws.receive_json()
            agents[agent_id]["last_seen"] = time.time()

            if data.get("type") == "proxy_response":
                rid = data["request_id"]
                if rid in pending:
                    pending[rid].set_result(data)

    except WebSocketDisconnect:
        print(f"[DISCONNECTED] {agent_id}")
        agents.pop(agent_id, None)

# ⚠️ مهم جدًا لRailway
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000))
    )
