from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.templating import Jinja2Templates
import asyncio, uuid, time

app = FastAPI()
templates = Jinja2Templates(directory="templates")

agents = {}      # agent_id -> {ws, last_seen, ip, city, country}
pending = {}     # request_id -> Future
OFFLINE_AFTER = 15  # seconds


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "agents": agents}
    )


@app.get("/agents")
async def agents_api():
    now = time.time()
    result = []
    for aid, a in agents.items():
        status = "online" if now - a["last_seen"] < OFFLINE_AFTER else "offline"
        result.append({
            "id": aid,
            "ip": a.get("ip"),
            "city": a.get("city"),
            "country": a.get("country"),
            "status": status
        })
    return result


@app.api_route("/proxy/{agent_id}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(agent_id: str, request: Request):
    if agent_id not in agents:
        return JSONResponse({"error": "Agent offline"}, status_code=404)

    target_url = request.query_params.get("url")
    if not target_url:
        return JSONResponse({"error": "Missing ?url="}, status_code=400)

    request_id = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    pending[request_id] = fut

    body = await request.body()

    await agents[agent_id]["ws"].send_json({
        "type": "proxy_request",
        "request_id": request_id,
        "method": request.method,
        "url": target_url,
        "headers": dict(request.headers),
        "body": body.decode("utf-8", errors="ignore")
    })

    try:
        res = await asyncio.wait_for(fut, timeout=40)
        return Response(
            content=res["body"].encode("utf-8", errors="ignore"),
            status_code=res["status"],
            headers=res["headers"]
        )
    except asyncio.TimeoutError:
        return JSONResponse({"error": "Agent timeout"}, status_code=504)
    finally:
        pending.pop(request_id, None)


@app.websocket("/ws/{agent_id}")
async def ws_endpoint(ws: WebSocket, agent_id: str):
    await ws.accept()
    agents[agent_id] = {
        "ws": ws,
        "last_seen": time.time(),
        "ip": ws.client.host,
        "city": agent_id.upper(),
        "country": "DZ"
    }
    print(f"[+] Agent connected: {agent_id}")

    try:
        while True:
            data = await ws.receive_json()
            agents[agent_id]["last_seen"] = time.time()

            if data.get("type") == "proxy_response":
                rid = data.get("request_id")
                if rid in pending and not pending[rid].done():
                    pending[rid].set_result(data)

    except WebSocketDisconnect:
        print(f"[-] Agent disconnected: {agent_id}")
