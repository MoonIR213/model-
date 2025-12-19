from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from datetime import datetime
import asyncio

app = FastAPI(title="Central Agent Control")

# ================== STORAGE ==================
clients = {}        # agent_id -> info
commands = {}       # agent_id -> command
connections = set() # websocket clients
# =============================================


# ================== UTILS ==================
async def broadcast():
    dead = set()
    for ws in connections:
        try:
            await ws.send_json(clients)
        except:
            dead.add(ws)
    connections.difference_update(dead)
# ===========================================


# ================== API ==================
@app.get("/")
def root():
    return {"status": "running", "time": str(datetime.now())}


@app.get("/agents")
def get_agents():
    return clients


@app.post("/register")
async def register(req: Request):
    data = await req.json()
    cid = data.get("agent_id")

    clients[cid] = {
        "ip": req.client.host,
        "hostname": data.get("hostname"),
        "local_ip": data.get("local_ip"),
        "started_at": data.get("started_at"),
        "last_seen": str(datetime.now()),
        "status": "online"
    }

    await broadcast()
    return {"registered": cid}


@app.post("/heartbeat")
async def heartbeat(req: Request):
    data = await req.json()
    cid = data.get("agent_id")

    if cid in clients:
        clients[cid]["last_seen"] = str(datetime.now())
        clients[cid]["status"] = "online"
        await broadcast()

    return {"ok": True}


@app.post("/command")
async def set_command(req: Request):
    data = await req.json()
    commands[data["agent_id"]] = data["command"]
    return {"sent": True}


@app.get("/command/{agent_id}")
def get_command(agent_id: str):
    cmd = commands.pop(agent_id, None)
    return {"command": cmd}
# ===========================================


# ================== WEBSOCKET ==================
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    connections.add(ws)

    # 🔥 أرسل الحالة الحالية فور الاتصال
    await ws.send_json(clients)

    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        connections.remove(ws)
# ===============================================


# ================== DASHBOARD ==================
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return """
<!DOCTYPE html>
<html>
<head>
<title>Agent Control Dashboard</title>
<style>
body { background:#0b0f14; color:#eee; font-family:Arial }
table { width:100%; border-collapse:collapse }
th,td { padding:8px; border-bottom:1px solid #222 }
.online { color:#4caf50 }
.offline { color:#f44336 }
</style>
</head>
<body>

<h2>Agent Control Dashboard</h2>
<input id="q" placeholder="Search hostname">

<table>
<thead>
<tr>
<th>ID</th><th>Hostname</th><th>Local IP</th><th>Status</th><th>Uptime</th><th>Action</th>
</tr>
</thead>
<tbody id="rows"></tbody>
</table>

<script>
let agents = {};

function uptime(start){
 if(!start) return '';
 let s=Math.floor((Date.now()-Date.parse(start))/1000);
 return Math.floor(s/60)+' min';
}

function render(){
 let q=document.getElementById('q').value.toLowerCase();
 let tbody=document.getElementById('rows');
 tbody.innerHTML='';
 Object.keys(agents).forEach(id=>{
  let a=agents[id];
  if(q && !(a.hostname||'').toLowerCase().includes(q)) return;
  let tr=document.createElement('tr');
  tr.innerHTML=`
   <td>${id.slice(0,8)}…</td>
   <td>${a.hostname||''}</td>
   <td>${a.local_ip||''}</td>
   <td class="${a.status}">${a.status}</td>
   <td>${uptime(a.started_at)}</td>
   <td><button onclick="ping('${id}')">Ping</button></td>
  `;
  tbody.appendChild(tr);
 });
}

function ping(id){
 fetch('/command',{
   method:'POST',
   headers:{'Content-Type':'application/json'},
   body:JSON.stringify({agent_id:id,command:'ping'})
 });
}

// 🔥 تحميل أولي
fetch('/agents')
 .then(r=>r.json())
 .then(data=>{
   agents=data;
   render();
 });

// 🔥 WebSocket
let ws=new WebSocket(
 (location.protocol==='https:'?'wss':'ws')+'://'+location.host+'/ws'
);
ws.onmessage=e=>{
 agents=JSON.parse(e.data);
 render();
};

document.getElementById('q').onkeyup=render;
</script>

</body>
</html>
"""
# ===============================================
