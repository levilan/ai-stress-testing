import asyncio
import aiohttp
import argparse
import time
import random
import statistics
import sys
import json

PROMPTS = [
    "請簡單介紹一下大語言模型的能力。",
    "請用三句話介紹壓測的基本思路。",
    "你好，請問你能幫我做些什麼？",
    "寫一段 Python 代碼來實現冒泡排序。",
    "解釋一下量子計算的基本原理。",
    "翻譯這句話成英文：'科技改變生活'。",
    "給我講一個關於程序員的冷笑話。",
    "什麼是 RESTful API？",
    "請列舉出五個常見的 HTTP 狀態碼及其含義。",
    "寫一首關於春天的詩。"
]

async def make_request(session, url, headers, payload, is_stream, metrics):
    start_time = time.time()
    m = metrics["stream"] if is_stream else metrics["non_stream"]
    
    try:
        async with session.post(url, json=payload, headers=headers) as response:
            status = response.status
            if is_stream:
                async for line in response.content:
                    if not line: break
            else:
                await response.text()
            
            latency = time.time() - start_time
            m["latencies"].append(latency)
            
            if status == 200:
                m["success"] += 1
            else:
                m["failed"] += 1
                error_key = f"HTTP {status}"
                m["errors"][error_key] = m["errors"].get(error_key, 0) + 1
                
                # 打印部分錯誤內容以便 Debug
                try:
                    err_text = await response.text()
                    print(f"[-] 請求失敗，狀態碼: {status}, 錯誤: {err_text[:200]}")
                except Exception:
                    pass
    except Exception as e:
        m["failed"] += 1
        error_name = type(e).__name__
        m["errors"][error_name] = m["errors"].get(error_name, 0) + 1

async def worker(queue, session, metrics):
    while True:
        task = await queue.get()
        if task is None:
            queue.task_done()
            break
        url, headers, payload, is_stream = task
        await make_request(session, url, headers, payload, is_stream, metrics)
        queue.task_done()

def get_stats(lats):
    if not lats: return None
    stats = {
        "mean": round(statistics.mean(lats), 4),
        "min": round(min(lats), 4),
        "max": round(max(lats), 4)
    }
    if len(lats) > 1:
        stats["p50"] = round(statistics.median(lats), 4)
        try:
            stats["p90"] = round(statistics.quantiles(lats, n=100)[89], 4)
            stats["p99"] = round(statistics.quantiles(lats, n=100)[98], 4)
        except:
            pass
    return stats

async def run_load_test(url, key, model, rpm, duration, mode, stream_ratio, workers_count=50):
    """核心壓測邏輯，返回結構化的數據"""
    base_url = f"{url}/v1beta/models/{model}:"
    stream_url = f"{base_url}streamGenerateContent?alt=sse"
    non_stream_url = f"{base_url}generateContent"

    metrics = {
        "stream": {"sent": 0, "success": 0, "failed": 0, "latencies": [], "errors": {}},
        "non_stream": {"sent": 0, "success": 0, "failed": 0, "latencies": [], "errors": {}}
    }

    interval = 60.0 / rpm if rpm > 0 else 0
    end_time = time.time() + duration
    queue = asyncio.Queue()
    timeout = aiohttp.ClientTimeout(total=120)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        workers = [asyncio.create_task(worker(queue, session, metrics)) for _ in range(workers_count)]
        
        try:
            while time.time() < end_time:
                loop_start = time.time()

                if mode == "stream": is_stream = True
                elif mode == "non-stream": is_stream = False
                else: is_stream = random.random() < stream_ratio

                # 隨機產生長度在 10 到 2000 之間的文本作為 input prompt
                target_length = random.randint(10, 2000)
                base_text = "這是一段用於測試大語言模型處理能力的長文本，我們希望通過不同長度的請求來測試 API 中轉平台的穩定性與響應速度。接下來是重複的內容以確保長度足夠：" * 100
                start_idx = random.randint(0, len(base_text) - target_length)
                prompt = base_text[start_idx : start_idx + target_length]
                payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
                headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
                
                if is_stream:
                    headers["Accept"] = "text/event-stream"
                    target_url = stream_url
                    metrics["stream"]["sent"] += 1
                else:
                    target_url = non_stream_url
                    metrics["non_stream"]["sent"] += 1

                queue.put_nowait((target_url, headers, payload, is_stream))

                if interval > 0:
                    elapsed = time.time() - loop_start
                    sleep_time = interval - elapsed
                    if sleep_time > 0:
                        await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            pass

        print(f"⏳ 測試時間結束，停止發送新請求。等待積壓請求處理 (最多 300 秒)...")
        
        try:
            await asyncio.wait_for(queue.join(), timeout=300.0)
        except asyncio.TimeoutError:
            print("⚠️ 目標伺服器響應過慢，導致請求大量積壓，已超時強制捨棄未完成的請求。")
            
        # 停止所有 worker
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

    return {
        "mode": mode,
        "duration": duration,
        "rpm": rpm,
        "stream": {
            "sent": metrics["stream"]["sent"],
            "success": metrics["stream"]["success"],
            "failed": metrics["stream"]["failed"],
            "stats": get_stats(metrics["stream"]["latencies"]),
            "raw_latencies": metrics["stream"]["latencies"],
            "errors": metrics["stream"]["errors"]
        },
        "non_stream": {
            "sent": metrics["non_stream"]["sent"],
            "success": metrics["non_stream"]["success"],
            "failed": metrics["non_stream"]["failed"],
            "stats": get_stats(metrics["non_stream"]["latencies"]),
            "raw_latencies": metrics["non_stream"]["latencies"],
            "errors": metrics["non_stream"]["errors"]
        }
    }

def print_latency_stats(name, stats_dict):
    print(f"\n⏳ {name} 響應時間統計:")
    if not stats_dict:
        print("  無數據")
        return
    for k, v in stats_dict.items():
        print(f"  {k.upper()}: {v:.4f} 秒")

async def cli_main():
    parser = argparse.ArgumentParser(description="API 中轉平台混合壓測工具")
    parser.add_argument("--url", required=True, help="接口基礎 URL (例如: https://your-domain.com)")
    parser.add_argument("--key", required=True, help="API Key")
    parser.add_argument("--model", default="gemini-3.1-pro-preview", help="模型名稱")
    parser.add_argument("--rpm", type=int, default=60, help="每分鐘請求總數 (RPM)")
    parser.add_argument("--duration", type=int, default=60, help="壓測持續時間 (秒)")
    parser.add_argument("--mode", choices=["stream", "non-stream", "mixed"], default="mixed", help="壓測模式 (默認: mixed)")
    parser.add_argument("--stream-ratio", type=float, default=0.5, help="混合模式下流式請求的佔比 (0.0~1.0，默認: 0.5)")
    parser.add_argument("--workers", type=int, default=50, help="最大併發協程數")
    parser.add_argument("--output-json", help="將結果導出為 JSON 文件")
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("🚀 開始壓測...")
    result = await run_load_test(
        args.url, args.key, args.model, args.rpm, args.duration, 
        args.mode, args.stream_ratio, args.workers
    )
    
    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)
        print(f"✅ 結果已保存至 {args.output_json}")

    print("\n" + "=" * 50)
    print("📊 壓測結果報告")
    print("=" * 50)
    
    s_data = result["stream"]
    ns_data = result["non_stream"]
    total_sent = s_data["sent"] + ns_data["sent"]
    total_success = s_data["success"] + ns_data["success"]
    total_failed = s_data["failed"] + ns_data["failed"]

    print(f"總請求數 (發出): {total_sent} (成功: {total_success}, 失敗: {total_failed})")
    
    if s_data["sent"] > 0:
        print(f"\n🌊 流式請求統計: 發出 {s_data['sent']}, 成功 {s_data['success']}, 失敗 {s_data['failed']}")
        print_latency_stats("流式 (Time to Last Byte)", s_data["stats"])

    if ns_data["sent"] > 0:
        print(f"\n📦 非流式請求統計: 發出 {ns_data['sent']}, 成功 {ns_data['success']}, 失敗 {ns_data['failed']}")
        print_latency_stats("非流式", ns_data["stats"])
    print("=" * 50)

if __name__ == "__main__":
    try:
        if sys.platform.startswith('win'):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(cli_main())
    except KeyboardInterrupt:
        print("\n[!] 用戶中斷壓測")