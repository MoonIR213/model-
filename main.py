from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncio, uuid, time

app = FastAPI()

templates = Jinja2Templates(directory="templates")

agents = {}              # agent_id -> websocket
agent_info = {}          # agent_id -> info
pending = {}             # request_id -> Future


# =========================
# UI
# =========================
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request
    })


@app.get("/api/agents")
async def api_agents():
    now = time.time()
    data = []
    for aid, info in agent_info.items():
        status = "online" if now - info["last_seen"] < 15 else "offline"
        data.append({
            "id": aid,
            "ip": info["ip"],
            "city": info["city"],
            "country": info["country"],
            "status": status
        })
    return data


# =========================
# HTTP / HTTPS TUNNEL
# =========================
@app.api_route("/proxy/{agent_id}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(agent_id: str, request: Request):

    if agent_id not in agents:
        return JSONResponse({"error": "Agent offline"}, status_code=404)

    request_id = str(uuid.uuid4())
    loop = asyncio.get_event_loop()
    fut = loop.create_future()
    pending[request_id] = fut

    body = await request.body()

    payload = {
        "type": "proxy_request",
        "request_id": request_id,
        "method": request.method,
        "url": str(request.url.query.split("url=")[-1]),
        "headers": dict(request.headers),
        "body": body.decode(errors="ignore")
    }

    await agents[agent_id].send_json(payload)

    try:
        resp = await asyncio.wait_for(fut, timeout=60)
        return JSONResponse(
            content=resp["body"],
            status_code=resp["status"],
            headers=resp["headers"]
        )
    except:
        return JSONResponse({"error": "timeout"}, status_code=504)


# =========================
# WebSocket (Agent)
# =========================
@app.websocket("/ws/{agent_id}")
async def ws_agent(ws: WebSocket, agent_id: str):
    await ws.accept()
    agents[agent_id] = ws

    agent_info[agent_id] = {
        "ip": ws.client.host,
        "city": "ORAN",
        "country": "DZ",
        "last_seen": time.time()
    }

    try:
        while True:
            data = await ws.receive_json()
            agent_info[agent_id]["last_seen"] = time.time()

            if data.get("type") == "proxy_response":
                rid = data["request_id"]
                if rid in pending:
                    pending[rid].set_result(data)
                    pending.pop(rid, None)

    except WebSocketDisconnect:
        agents.pop(agent_id, None)
