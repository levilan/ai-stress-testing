#!/bin/bash
set -e

if [ ! -f "aws_resources.env" ]; then
    echo "❌ 錯誤: 找不到 aws_resources.env 文件！"
    echo "💡 請先執行 ./aws_deploy.sh 來建立 EC2 資源與環境變數。"
    exit 1
fi

source aws_resources.env

if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Usage: ./aws_run_test.sh <API_URL> <API_KEY>"
    exit 1
fi

API_URL="$1"
API_KEY="$2"
RPM=600
DURATION=120

echo "🚀 [3.5/7] 更新節點上的壓測腳本..."
scp -o StrictHostKeyChecking=no -i "${KEY_NAME}.pem" load_test.py "ec2-user@$NODE1_IP:~/"
scp -o StrictHostKeyChecking=no -i "${KEY_NAME}.pem" load_test.py "ec2-user@$NODE2_IP:~/"
scp -o StrictHostKeyChecking=no -i "${KEY_NAME}.pem" load_test.py "ec2-user@$NODE3_IP:~/"

echo "🚀 [4/7] 觸發 3 台 EC2 進行分散式並發壓測..."
echo "每台將產生 $RPM RPM，持續 $DURATION 秒..."

# 同步執行壓測，我們這裡不用 nohup 而是直接讓 ssh 前景執行，以便準確知道何時跑完
ssh -o StrictHostKeyChecking=no -i "${KEY_NAME}.pem" "ec2-user@$NODE1_IP" "python3 load_test.py --url \"$API_URL\" --key \"$API_KEY\" --rpm $RPM --duration $DURATION --mode mixed --workers 100 --output-json result.json > test_result.log 2>&1" &
P1=$!

ssh -o StrictHostKeyChecking=no -i "${KEY_NAME}.pem" "ec2-user@$NODE2_IP" "python3 load_test.py --url \"$API_URL\" --key \"$API_KEY\" --rpm $RPM --duration $DURATION --mode mixed --workers 100 --output-json result.json > test_result.log 2>&1" &
P2=$!

ssh -o StrictHostKeyChecking=no -i "${KEY_NAME}.pem" "ec2-user@$NODE3_IP" "python3 load_test.py --url \"$API_URL\" --key \"$API_KEY\" --rpm $RPM --duration $DURATION --mode mixed --workers 100 --output-json result.json > test_result.log 2>&1" &
P3=$!

echo "✅ 壓測已在遠端啟動！正在等待壓測完成 (約需 $(($DURATION + 20)) 秒)..."
wait $P1
wait $P2
wait $P3
echo "✅ 遠端壓測執行結束！"

echo "🚀 [5/7] 收集測試報告與 JSON 數據..."
# 允許 scp 失敗不中斷腳本，因為有 trap 會保底回收
set +e
scp -o StrictHostKeyChecking=no -i "${KEY_NAME}.pem" "ec2-user@$NODE1_IP:~/test_result.log" "node1_result.log"
scp -o StrictHostKeyChecking=no -i "${KEY_NAME}.pem" "ec2-user@$NODE1_IP:~/result.json" "node1.json"
scp -o StrictHostKeyChecking=no -i "${KEY_NAME}.pem" "ec2-user@$NODE2_IP:~/test_result.log" "node2_result.log"
scp -o StrictHostKeyChecking=no -i "${KEY_NAME}.pem" "ec2-user@$NODE2_IP:~/result.json" "node2.json"
scp -o StrictHostKeyChecking=no -i "${KEY_NAME}.pem" "ec2-user@$NODE3_IP:~/test_result.log" "node3_result.log"
scp -o StrictHostKeyChecking=no -i "${KEY_NAME}.pem" "ec2-user@$NODE3_IP:~/result.json" "node3.json"
set -e

echo "✅ 報告已收集到本地。"

echo "🚀 [5.5/7] 產生合併 HTML 報表..."
if [ -f "node1.json" ] || [ -f "node2.json" ] || [ -f "node3.json" ]; then
    python3 generate_report.py node1.json node2.json node3.json merged_report.html
    echo "✅ 已經成功生成: merged_report.html"
else
    echo "❌ 找不到 JSON 報告，合併失敗。請檢查 node1_result.log 內的錯誤。"
fi

echo "=========================================="
echo "🎯 節點 1 報告 (部分摘要):"
tail -n 25 node1_result.log || true
echo "=========================================="
echo "🎯 節點 2 報告 (部分摘要):"
tail -n 25 node2_result.log || true
echo "=========================================="
echo "🎯 節點 3 報告 (部分摘要):"
tail -n 25 node3_result.log || true
echo "=========================================="
echo "✅ 壓測與報告生成完畢！"
echo "💡 (機器仍然保持開啟狀態。若要再次測試，可直接重新執行此腳本)"
echo "⚠️ 若測試完全結束，請務必執行 ./aws_destroy.sh 來關閉機器以避免產生費用！"
