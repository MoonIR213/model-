import asyncio, os, time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials

app = FastAPI()
templates = Jinja2Templates(directory="templates")
security = HTTPBasic()

ADMIN_PASSWORD = "041420521"

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.password != ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong Password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

agents = {}        
agent_info = {}    
client_links = {}  

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, _ = Depends(authenticate)):
    now = time.time()
    # تنظيف القائمة من الوكلاء غير المتصلين (أكثر من 60 ثانية خمول)
    active_agents = {aid: info for aid, info in agent_info.items() if now - info["last_seen"] < 60}
    return templates.TemplateResponse("index.html", {"request": request, "agents": active_agents, "now": now})

@app.websocket("/ws/agent/{agent_id}")
async def ws_agent(ws: WebSocket, agent_id: str):
    await ws.accept()
    agents[agent_id] = ws
    agent_info[agent_id] = {"ip": ws.client.host, "last_seen": time.time()}
    print(f"[+] Agent Connected: {agent_id}")
    
    try:
        while True:
            # انتظار البيانات مع مهلة 90 ثانية. إذا لم تصل بيانات، يتم فصله.
            data = await asyncio.wait_for(ws.receive_bytes(), timeout=90)
            agent_info[agent_id]["last_seen"] = time.time()
            
            # إذا كانت الرسالة "ping" من العميل، نتجاهلها (فقط لتحديث الـ last_seen)
            if data == b"heartbeat":
                continue

            if len(data) > 16:
                target_id, payload = data[:16], data[16:]
                for c_ws, (a_ws, c_id) in list(client_links.items()):
                    if a_ws == ws and c_id == target_id:
                        try:
                            await c_ws.send_bytes(payload)
                        except:
                            client_links.pop(c_ws, None)
    except Exception as e:
        print(f"[-] Agent {agent_id} disconnected: {e}")
    finally:
        agents.pop(agent_id, None)
        agent_info.pop(agent_id, None)

@app.websocket("/ws/client/{agent_id}")
async def ws_client(ws: WebSocket, agent_id: str):
    await ws.accept()
    agent_ws = agents.get(agent_id)
    if not agent_ws:
        await ws.close()
        return
    
    c_id = os.urandom(16)
    client_links[ws] = (agent_ws, c_id)
    print(f"[*] New Client Link via Agent: {agent_id}")

    try:
        while True:
            payload = await ws.receive_bytes()
            await agent_ws.send_bytes(c_id + payload)
    except:
        pass
    finally:
        client_links.pop(ws, None)

if __name__ == "__main__":
    import uvicorn
    # إعدادات uvicorn مهمة جداً لثبات الـ WebSockets
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), ws_ping_interval=20, ws_ping_timeout=20)
