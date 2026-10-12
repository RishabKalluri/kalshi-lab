#!/usr/bin/env bash
# Research server (EC2 kalshi-research, auto-stops after 30 idle minutes).
#   deploy/research.sh start|stop|status
# start: boots it, waits for SSH, and points the `kalshi-research` SSH alias at its new IP.
set -euo pipefail
IID=$(aws ec2 describe-instances --filters Name=tag:Name,Values=kalshi-research Name=instance-state-name,Values=pending,running,stopping,stopped \
      --query 'Reservations[0].Instances[0].InstanceId' --output text)
case "${1:-status}" in
  start)
    # SSH is only open to this laptop's current IP (it changes with the network): replace the rule
    SG=$(aws ec2 describe-instances --instance-ids "$IID" --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' --output text)
    ME=$(curl -s -m 10 https://checkip.amazonaws.com)/32
    OLD=$(aws ec2 describe-security-groups --group-ids "$SG" --query 'SecurityGroups[0].IpPermissions[?FromPort==`22`].IpRanges[].CidrIp' --output text)
    for c in $OLD; do [ "$c" = "$ME" ] || aws ec2 revoke-security-group-ingress --group-id "$SG" --protocol tcp --port 22 --cidr "$c" >/dev/null; done
    echo "$OLD" | grep -qw "$ME" || aws ec2 authorize-security-group-ingress --group-id "$SG" --protocol tcp --port 22 --cidr "$ME" >/dev/null
    aws ec2 start-instances --instance-ids "$IID" >/dev/null
    aws ec2 wait instance-running --instance-ids "$IID"
    IP=$(aws ec2 describe-instances --instance-ids "$IID" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
    sed -i '' "/^Host kalshi-research$/,/^Host /s/^    HostName .*/    HostName $IP/" ~/.ssh/config
    ssh-keygen -R "$IP" >/dev/null 2>&1 || true
    until ssh -o ConnectTimeout=5 -o BatchMode=yes kalshi-research true 2>/dev/null; do sleep 5; done
    echo "kalshi-research up at $IP" ;;
  stop) aws ec2 stop-instances --instance-ids "$IID" >/dev/null && echo stopping ;;
  status) aws ec2 describe-instances --instance-ids "$IID" --query 'Reservations[0].Instances[0].[InstanceType,State.Name,PublicIpAddress]' --output text ;;
esac
