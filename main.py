from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Response
import asyncio
import base64
import uuid

app = FastAPI()
agents = {}

@app.websocket("/ws/oran_pc")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    agents["main"] = websocket
    print("[*] تم ربط حاسوب وهران بنجاح")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        agents.pop("main", None)
        print("[!] فقد الاتصال بحاسوب وهران")

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def universal_proxy(request: Request, path: str):
    if "main" not in agents:
        return Response("خطأ: حاسوب وهران غير متصل حالياً", status_code=503)

    # تجهيز الطلب القادم من بشار
    body = await request.body()
    target_url = str(request.url)
    ws = agents["main"]
    task_id = str(uuid.uuid4())

    # إرسال البيانات عبر النفق
    await ws.send_json({
        "task_id": task_id,
        "url": target_url,
        "method": request.method,
        "body": base64.b64encode(body).decode('utf-8'),
        "headers": dict(request.headers)
    })

    try:
        # انتظار الرد من وهران (timeout 30 ثانية للطلبات الثقيلة)
        response_data = await asyncio.wait_for(ws.receive_json(), timeout=30)
        content = base64.b64decode(response_data["content"])
        
        return Response(
            content=content,
            status_code=response_data["status"],
            headers=response_data["headers"]
        )
    except Exception:
        return Response("فشل الاتصال عبر نفق وهران", status_code=504)
