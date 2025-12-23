from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import Response, JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
import asyncio, uuid, time

app = FastAPI()
templates = Jinja2Templates(directory="templates")

agents = {}       # agent_id -> {ws, last_seen}
pending = {}      # request_id -> Future
OFFLINE_AFTER = 15

# =========================
# UI
# =========================
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# =========================
# API
# =========================
@app.get("/agents")
async def get_agents():
    now = time.time()
    out = []
    for aid, a in agents.items():
        out.append({
            "agent_id": aid,
            "status": "online" if now - a["last_seen"] <= OFFLINE_AFTER else "offline",
            "last_seen": int(now - a["last_seen"])
        })
    return out

# =========================
# PROXY TUNNEL
# =========================
@app.api_route("/proxy/{agent_id}", methods=["GET","POST","PUT","DELETE","PATCH","OPTIONS"])
async def proxy(agent_id: str, request: Request):
    if agent_id not in agents:
        return JSONResponse({"error": "Agent offline"}, status_code=404)

    url = request.query_params.get("url")
    if not url:
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
        "url": url,
        "headers": dict(request.headers),
        "body": body.decode(errors="ignore")
    }

    await agents[agent_id]["ws"].send_json(payload)

    try:
        resp = await asyncio.wait_for(fut, timeout=60)
        return Response(
            content=resp["body"],
            status_code=resp["status"],
            headers=resp["headers"]
        )
    except asyncio.TimeoutError:
        return JSONResponse({"error": "Timeout"}, status_code=504)
    finally:
        pending.pop(req_id, None)

# =========================
# WEBSOCKET
# =========================
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
