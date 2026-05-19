#!/bin/bash
set -e

# 設定參數
REGION="us-east-1"
PROFILE="default"
INSTANCE_TYPE="t3.medium" # 2 vCPU, 4GB RAM
AMI_ID="ami-0d5a4838bc1cd4146" # AL2023 x86_64
KEY_NAME="load-test-key-$(date +%s)"
SG_NAME="load-test-sg-$(date +%s)"

echo "🚀 [1/7] 準備 AWS 環境資源..."

# 1. 創建 SSH Key Pair 並保存到本地
aws ec2 create-key-pair \
    --key-name "$KEY_NAME" \
    --query 'KeyMaterial' \
    --output text \
    --region "$REGION" \
    --profile "$PROFILE" > "${KEY_NAME}.pem"
chmod 400 "${KEY_NAME}.pem"
echo "✅ SSH 密鑰已建立: ${KEY_NAME}.pem"

# 2. 創建 Security Group (允許 SSH 連線)
VPC_ID=$(aws ec2 describe-vpcs --region "$REGION" --profile "$PROFILE" --query 'Vpcs[0].VpcId' --output text)
SG_ID=$(aws ec2 create-security-group \
    --group-name "$SG_NAME" \
    --description "SG for Load Testing" \
    --vpc-id "$VPC_ID" \
    --region "$REGION" \
    --profile "$PROFILE" \
    --query 'GroupId' --output text)

# 獲取本機的公網 IP 為了安全限制 SSH
MY_IP=$(curl -s http://checkip.amazonaws.com)
aws ec2 authorize-security-group-ingress \
    --group-id "$SG_ID" \
    --protocol tcp \
    --port 22 \
    --cidr "${MY_IP}/32" \
    --region "$REGION" \
    --profile "$PROFILE" > /dev/null
echo "✅ Security Group 已建立: $SG_ID"

echo "🚀 [2/7] 啟動 3 台 EC2 實例 (t3.medium)..."
INSTANCE_IDS=$(aws ec2 run-instances \
    --image-id "$AMI_ID" \
    --count 3 \
    --instance-type "$INSTANCE_TYPE" \
    --key-name "$KEY_NAME" \
    --security-group-ids "$SG_ID" \
    --associate-public-ip-address \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=LoadTest-Node}]" \
    --region "$REGION" \
    --profile "$PROFILE" \
    --query 'Instances[*].InstanceId' --output text)

echo "實例 ID: $INSTANCE_IDS"
echo "⏳ 等待實例啟動並獲取公網 IP (約需 30-60 秒)..."
aws ec2 wait instance-running --instance-ids $INSTANCE_IDS --region "$REGION" --profile "$PROFILE"

IPS=($(aws ec2 describe-instances \
    --instance-ids $INSTANCE_IDS \
    --region "$REGION" \
    --profile "$PROFILE" \
    --query 'Reservations[*].Instances[*].PublicIpAddress' \
    --output text))

echo "✅ 節點 1 IP: ${IPS[0]}"
echo "✅ 節點 2 IP: ${IPS[1]}"
echo "✅ 節點 3 IP: ${IPS[2]}"

# 儲存資訊供後續清理
echo "INSTANCE_IDS=\"$INSTANCE_IDS\"" > aws_resources.env
echo "KEY_NAME=\"$KEY_NAME\"" >> aws_resources.env
echo "SG_ID=\"$SG_ID\"" >> aws_resources.env
echo "NODE1_IP=\"${IPS[0]}\"" >> aws_resources.env
echo "NODE2_IP=\"${IPS[1]}\"" >> aws_resources.env
echo "NODE3_IP=\"${IPS[2]}\"" >> aws_resources.env

echo "⏳ 等待 SSH 服務就緒 (30 秒)..."
sleep 30

echo "🚀 [3/7] 部署壓測腳本與環境..."
for i in {0..2}; do
    IP=${IPS[$i]}
    echo "配置節點: $IP"
    # 自動接受 SSH 憑證
    ssh-keyscan -H "$IP" >> ~/.ssh/known_hosts 2>/dev/null
    
    # 傳輸腳本
    scp -i "${KEY_NAME}.pem" load_test.py "ec2-user@$IP:~/"
    
    # 安裝 Python 依賴
    ssh -i "${KEY_NAME}.pem" "ec2-user@$IP" "sudo dnf install -y python3-pip && pip3 install aiohttp" > /dev/null 2>&1
done
echo "✅ 環境部署完成。"
