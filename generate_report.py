import sys
import json
import statistics

def calc_stats(lats):
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

def main():
    if len(sys.argv) < 3:
        print("Usage: python generate_report.py <node1.json> [node2.json...] <output.html>")
        sys.exit(1)
        
    json_files = sys.argv[1:-1]
    out_file = sys.argv[-1]

    merged = {
        "stream": {"sent": 0, "success": 0, "failed": 0, "raw_latencies": [], "errors": {}},
        "non_stream": {"sent": 0, "success": 0, "failed": 0, "raw_latencies": [], "errors": {}}
    }
    
    total_nodes = len(json_files)
    total_duration = 0

    for f in json_files:
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
                total_duration = data.get("duration", total_duration) # 取其中一個即可，都是同時跑
                for key in ["stream", "non_stream"]:
                    if key in data:
                        merged[key]["sent"] += data[key]["sent"]
                        merged[key]["success"] += data[key]["success"]
                        merged[key]["failed"] += data[key]["failed"]
                        merged[key]["raw_latencies"].extend(data[key].get("raw_latencies", []))
                        for err_k, err_v in data[key].get("errors", {}).items():
                            merged[key]["errors"][err_k] = merged[key]["errors"].get(err_k, 0) + err_v
        except Exception as e:
            print(f"[-] 讀取文件 {f} 失敗: {e}")

    s_stats = calc_stats(merged["stream"]["raw_latencies"]) or {}
    ns_stats = calc_stats(merged["non_stream"]["raw_latencies"]) or {}
    
    total_sent = merged["stream"]["sent"] + merged["non_stream"]["sent"]
    total_success = merged["stream"]["success"] + merged["non_stream"]["success"]
    total_failed = merged["stream"]["failed"] + merged["non_stream"]["failed"]
    total_failure_rate = (total_failed / total_sent * 100) if total_sent > 0 else 0

    # 合併總錯誤統計
    total_errors = {}
    for key in ["stream", "non_stream"]:
        for err_k, err_v in merged[key]["errors"].items():
            total_errors[err_k] = total_errors.get(err_k, 0) + err_v

    # 渲染錯誤區塊
    error_html = ""
    if total_errors:
        error_items = "".join([f'<li class="flex justify-between py-2 border-b border-red-100 last:border-0"><span class="font-mono text-red-700">{k}</span> <span class="font-bold text-red-600">{v} 次</span></li>' for k, v in sorted(total_errors.items(), key=lambda x: x[1], reverse=True)])
        error_html = f"""
        <div class="mt-8 bg-red-50 rounded-xl shadow-md p-6 border border-red-200">
            <h3 class="text-xl font-bold mb-4 text-red-700">🚨 錯誤紀錄彙總</h3>
            <ul class="text-sm">
                {error_items}
            </ul>
        </div>
        """

    # 渲染 HTML (沿用相似 Tailwind 模板)
    def render_card(title, color, prefix, data, stats):
        if data["sent"] == 0: return ""
        items = "".join([f'<li class="flex justify-between border-b border-gray-100 pb-2"><span class="text-gray-600">{k.upper()}:</span> <span class="font-mono font-semibold">{v} s</span></li>' for k, v in stats.items()])
        failure_rate = (data['failed'] / data['sent'] * 100) if data['sent'] > 0 else 0
        return f"""
        <div class="bg-white rounded-xl shadow p-6 border-t-4 border-{color}-500">
            <h3 class="text-xl font-bold mb-4 text-{color}-600">{title}</h3>
            <div class="grid grid-cols-4 gap-4 mb-6 text-center">
                <div class="bg-gray-50 p-2 rounded"><div class="text-sm text-gray-500">發出</div><div class="font-bold text-lg">{data['sent']}</div></div>
                <div class="bg-green-50 p-2 rounded"><div class="text-sm text-green-600">成功</div><div class="font-bold text-lg text-green-600">{data['success']}</div></div>
                <div class="bg-red-50 p-2 rounded"><div class="text-sm text-red-600">失敗</div><div class="font-bold text-lg text-red-600">{data['failed']}</div></div>
                <div class="bg-red-100 p-2 rounded"><div class="text-sm text-red-700">失敗率</div><div class="font-bold text-lg text-red-700">{failure_rate:.1f}%</div></div>
            </div>
            <div>
                <h4 class="text-sm font-semibold text-gray-700 mb-4 border-b pb-1">響應時間統計</h4>
                <ul class="text-sm space-y-3">{items}</ul>
            </div>
        </div>
        """

    html = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>API 雲端壓測合併報告</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-50 min-h-screen text-gray-800 font-sans p-6 md:p-12">
        <div class="max-w-4xl mx-auto">
            <div class="text-center mb-10">
                <h1 class="text-4xl font-extrabold text-blue-600 mb-2">☁️ 分散式壓測合併報告</h1>
                <p class="text-gray-500">來自 {total_nodes} 台 EC2 節點的數據匯總 (壓測時間: {total_duration} 秒)</p>
            </div>
            
            <div class="bg-white rounded-xl shadow-md p-6 mb-8 border border-gray-100 flex justify-around text-center">
                <div><div class="text-gray-500 text-sm">總請求發送</div><div class="text-2xl font-bold">{total_sent}</div></div>
                <div><div class="text-gray-500 text-sm">總成功</div><div class="text-2xl font-bold text-green-600">{total_success}</div></div>
                <div><div class="text-gray-500 text-sm">總失敗</div><div class="text-2xl font-bold text-red-600">{total_failed}</div></div>
                <div><div class="text-gray-500 text-sm">總失敗率</div><div class="text-2xl font-bold text-red-700">{total_failure_rate:.1f}%</div></div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                {render_card("🌊 流式請求 (SSE)", "blue", "s", merged["stream"], s_stats)}
                {render_card("📦 非流式請求", "purple", "ns", merged["non_stream"], ns_stats)}
            </div>
            
            {error_html}

            <div class="mt-8 bg-gray-50 rounded-xl shadow-sm p-6 border border-gray-200">
                <h3 class="text-lg font-bold mb-3 text-gray-700">📖 常見錯誤碼對照表</h3>
                <ul class="text-sm text-gray-600 space-y-2">
                    <li><strong class="text-gray-800">HTTP 429 (Too Many Requests):</strong> 目標 API 已觸發限流機制，這表示當前的發送速率 (RPM) 已超過中轉平台或供應商的處理上限。</li>
                    <li><strong class="text-gray-800">HTTP 502 / 503 / 504:</strong> 網關或服務器過載。通常代表中轉平台的負載均衡器無法連接到後端，服務可能處於卡死或重啟狀態。</li>
                    <li><strong class="text-gray-800">HTTP 500 (Internal Server Error):</strong> 目標中轉平台內部代碼報錯（例如：資料庫連線超時、處理請求時發生異常）。</li>
                    <li><strong class="text-gray-800">TimeoutError / ClientConnectorError:</strong> 網路層級的連線中斷。這代表伺服器連「HTTP 回應」都來不及回傳，連線就被迫斷開，通常發生在極度嚴重的塞車或網路頻寬被打滿時。</li>
                </ul>
                <p class="mt-4 text-xs text-gray-500">💡 提示: 若要查看具體的報錯字串內容，請打開測試結束後自動抓回本地的 <code>nodeX_result.log</code> 日誌檔。</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(html)
        
    print(f"✅ 合併報表已成功生成: {out_file}")

if __name__ == "__main__":
    main()