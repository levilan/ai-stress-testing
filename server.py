import sys
import asyncio
from aiohttp import web
from load_test import run_load_test

async def index_handler(request):
    """提供前端 HTML 頁面"""
    return web.FileResponse('./index.html')

async def api_run_handler(request):
    """處理前端發送的壓測請求"""
    try:
        data = await request.json()
        
        # 解析並校驗參數
        url = data.get('url')
        key = data.get('key')
        if not url or not key:
            return web.json_response({"status": "error", "message": "URL 和 API Key 是必填項"}, status=400)
            
        model = data.get('model', 'gemini-3.1-pro-preview')
        rpm = int(data.get('rpm', 60))
        duration = int(data.get('duration', 60))
        mode = data.get('mode', 'mixed')
        stream_ratio = float(data.get('stream_ratio', 0.5))
        workers = int(data.get('workers', 50))

        # 調用核心壓測函數
        result = await run_load_test(
            url=url,
            key=key,
            model=model,
            rpm=rpm,
            duration=duration,
            mode=mode,
            stream_ratio=stream_ratio,
            workers_count=workers
        )
        
        return web.json_response({"status": "success", "data": result})
        
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=500)

app = web.Application()
# 設置路由
app.router.add_get('/', index_handler)
app.router.add_post('/api/run', api_run_handler)

if __name__ == "__main__":
    print("=" * 50)
    print("🌟 壓測 Web UI 啟動成功！")
    print("👉 請在瀏覽器打開: http://localhost:8080")
    print("=" * 50)
    
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    web.run_app(app, port=8080, print=None)