#!/usr/bin/env bash
# ============================================================================
# 眼健康自查助手 · 卸载脚本
# @author  杨博 (yangbo621@163.com)
# @license Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)
#          https://creativecommons.org/licenses/by-nc/4.0/
# （详见随包 LICENSE.txt / NOTICE.md；商业使用需另行获得书面授权）
# ============================================================================

# ==============================================================================
# 中医眼科辨证智能体 · 卸载脚本
#   用法：sudo bash uninstall.sh [--purge] [--dir /opt/eye-agent]
#   --purge  同时删除数据与报告（默认保留，便于重装后恢复历史档案）
# ==============================================================================
set -euo pipefail

INSTALL_DIR="/opt/eye-agent"
DATA_DIR="/var/lib/eye-agent"
LOG_DIR="/var/log/eye-agent"
SERVICE_USER="eye-agent"
PURGE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --purge)    PURGE=1; shift ;;
    --dir)      INSTALL_DIR="${2:?--dir 需要参数}"; shift 2 ;;
    -h|--help)  echo "用法：sudo bash uninstall.sh [--purge] [--dir PATH]"; exit 0 ;;
    *)          echo "未知参数：$1"; exit 1 ;;
  esac
done

[ "$(id -u)" -eq 0 ] || { echo "请用 root 执行：sudo bash uninstall.sh"; exit 1; }

echo "▸ 停止并移除服务"
if command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
  systemctl stop eye-agent 2>/dev/null || true
  systemctl disable eye-agent 2>/dev/null || true
  rm -f /etc/systemd/system/eye-agent.service
  systemctl daemon-reload 2>/dev/null || true
else
  pkill -f "uvicorn app:app" 2>/dev/null || true
fi
rm -f /usr/local/bin/eye-agent
echo "✔ 服务已移除"

echo "▸ 删除程序目录 $INSTALL_DIR"
rm -rf "$INSTALL_DIR"
rm -f /etc/eye-agent.env
echo "✔ 程序已删除"

if [ "$PURGE" = "1" ]; then
  echo "▸ 删除数据与日志（--purge）"
  rm -rf "$DATA_DIR" "$LOG_DIR"
  if id -u "$SERVICE_USER" >/dev/null 2>&1; then userdel "$SERVICE_USER" 2>/dev/null || true; fi
  echo "✔ 数据、日志与运行用户已删除（历史报告不可恢复）"
else
  echo
  echo "⚠ 已保留数据：$DATA_DIR（档案 records.json + 全部报告）"
  echo "  如需彻底清除：sudo bash uninstall.sh --purge"
fi

echo
echo "════════ 卸载完成 ════════"
