from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Response
import asyncio
import base64
import uuid
import os

app = FastAPI()
agents = {}
pending_tasks = {} # قاموس لتخزين الوعود (Futures) الخاصة بكل طلب

@app.get("/")
async def status():
    return {"status": "Online", "agent_connected": "main" in agents}

@app.websocket("/ws/oran_pc")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    agents["main"] = websocket
    print("[*] Agent Connected via ASGI")
    try:
        while True:
            # استقبال الردود من وهران وتوجيهها للطلب الصحيح
            data = await websocket.receive_json()
            task_id = data.get("task_id")
            if task_id in pending_tasks:
                # تسليم النتيجة للـ Future المنتظر في دالة proxy_handler
                pending_tasks[task_id].set_result(data)
    except WebSocketDisconnect:
        agents.pop("main", None)

@app.api_route("/proxy", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_handler(request: Request, target_url: str):
    if "main" not in agents:
        return Response("Error: Oran Agent Offline", status_code=503)

    task_id = str(uuid.uuid4())
    body = await request.body()
    
    # إنشاء "وعد" (Future) لهذا الطلب تحديداً
    loop = asyncio.get_event_loop()
    future = loop.create_future()
    pending_tasks[task_id] = future

    try:
        # إرسال الطلب لوهران
        await agents["main"].send_json({
            "task_id": task_id,
            "url": target_url,
            "method": request.method,
            "body": base64.b64encode(body).decode('utf-8'),
            "headers": dict(request.headers)
        })

        # انتظار الرد الخاص بهذا الـ task_id فقط
        response_data = await asyncio.wait_for(future, timeout=30)
        content = base64.b64decode(response_data["content"])
        return Response(
            content=content,
            status_code=response_data["status"],
            headers=response_data.get("headers", {})
        )
    except Exception as e:
        return Response(f"Proxy Error: {str(e)}", status_code=504)
    finally:
        # تنظيف القاموس بعد الانتهاء
        pending_tasks.pop(task_id, None)

# تشغيل السيرفر بشكل صحيح ليدعم الـ WebSocket على Railway
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
