#!/bin/bash

if [ ! -f "aws_resources.env" ]; then
    echo "✅ 目前沒有發現活躍的資源 (找不到 aws_resources.env)。"
    exit 0
fi

source aws_resources.env

echo "🚀 [清理] 開始終止 AWS 資源..."
aws ec2 terminate-instances --instance-ids $INSTANCE_IDS --region us-east-1 > /dev/null || true
echo "⏳ 等待實例完全終止以便刪除 Security Group..."
aws ec2 wait instance-terminated --instance-ids $INSTANCE_IDS --region us-east-1 || true

aws ec2 delete-security-group --group-id "$SG_ID" --region us-east-1 || true
aws ec2 delete-key-pair --key-name "$KEY_NAME" --region us-east-1 || true
rm -f "${KEY_NAME}.pem" aws_resources.env

echo "✅ 資源已徹底清理完畢。再也不會產生費用！"
