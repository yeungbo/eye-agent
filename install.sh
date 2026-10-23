#!/usr/bin/env bash
# ============================================================================
# 眼健康自查助手 · Linux 一键安装脚本
# @author  杨博 (yangbo621@163.com)
# @license Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)
#          https://creativecommons.org/licenses/by-nc/4.0/
# （详见随包 LICENSE.txt / NOTICE.md；商业使用需另行获得书面授权）
# ============================================================================

# ==============================================================================
# 眼健康自查助手 · Ubuntu / Debian 一键安装脚本
# 离线自包含：内置知识库与依赖 wheel，装完即可用，全程不联网（除非缺 wheel）
# 用法：sudo bash install.sh [--port 8765] [--host 0.0.0.0] [--dir /opt/eye-agent]
# ==============================================================================
set -euo pipefail

# ---------- 默认配置（可用命令行参数覆盖） ----------
INSTALL_DIR="/opt/eye-agent"
DATA_DIR="/var/lib/eye-agent"
LOG_DIR="/var/log/eye-agent"
SERVICE_USER="eye-agent"
EYE_HOST="0.0.0.0"
EYE_PORT="8765"
USE_SYSTEMD="auto"
PIP_MODE="auto"          # auto | offline | online
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------- 输出样式 ----------
if [ -t 1 ]; then
  C_G=$'\033[32m'; C_Y=$'\033[33m'; C_R=$'\033[31m'; C_B=$'\033[1m'; C_0=$'\033[0m'
else
  C_G=""; C_Y=""; C_R=""; C_B=""; C_0=""
fi
info()  { printf "${C_G}✔${C_0} %s\n" "$*"; }
warn()  { printf "${C_Y}⚠${C_0} %s\n" "$*"; }
err()   { printf "${C_R}✘${C_0} %s\n" "$*" >&2; }
step()  { printf "\n${C_B}▸ %s${C_0}\n" "$*"; }
die()   { err "$*"; exit 1; }

usage() {
  cat <<EOF
用法：sudo bash install.sh [选项]

  --port N          服务端口（默认 8765）
  --host ADDR       监听地址（默认 0.0.0.0，局域网可访问）
  --dir PATH        安装目录（默认 /opt/eye-agent）
  --offline         强制离线安装（只用内置 wheel）
  --online          强制联网安装（忽略内置 wheel）
  --no-systemd      不注册 systemd，改用后台进程方式启动
  -h, --help        显示本帮助

安装内容：
  程序      ${INSTALL_DIR}/{app,references,venv}
  数据      ${DATA_DIR}/{data,reports}          （报告与档案，升级/重装不丢）
  日志      ${LOG_DIR}/
  配置      /etc/eye-agent.env
  服务      /etc/systemd/system/eye-agent.service
  命令      /usr/local/bin/eye-agent
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --port)      EYE_PORT="${2:?--port 需要参数}"; shift 2 ;;
    --host)      EYE_HOST="${2:?--host 需要参数}"; shift 2 ;;
    --dir)       INSTALL_DIR="${2:?--dir 需要参数}"; shift 2 ;;
    --offline)   PIP_MODE="offline"; shift ;;
    --online)    PIP_MODE="online"; shift ;;
    --no-systemd) USE_SYSTEMD="no"; shift ;;
    -h|--help)   usage; exit 0 ;;
    *)           die "未知参数：$1（用 --help 查看用法）" ;;
  esac
done

# ---------- 0. 前置检查 ----------
step "0/7 检查运行环境"
[ "$(id -u)" -eq 0 ] || die "请用 root 执行：sudo bash install.sh"

command -v python3 >/dev/null 2>&1 || die "未找到 python3，请先安装：sudo apt install -y python3"
PY_OK=$(python3 -c 'import sys; print(1 if sys.version_info>=(3,9) else 0)')
PY_VER=$(python3 -c 'import sys; print("%d.%d"%sys.version_info[:2])')
[ "$PY_OK" = "1" ] || die "Python 版本过低（当前 $PY_VER），需要 >= 3.9"
info "Python $PY_VER"

[ -f "$SRC_DIR/app/backend/app.py" ]   || die "缺少 app/backend/app.py，请在安装包根目录执行本脚本"
[ -d "$SRC_DIR/references" ]           || die "缺少 references/ 知识库目录"
info "安装包完整（知识库 $(du -sh "$SRC_DIR/references" 2>/dev/null | cut -f1)）"

# venv / pip 可用性（Debian 系默认不带 venv）
if ! python3 -m venv --help >/dev/null 2>&1; then
  warn "python3-venv 缺失，尝试自动安装…"
  if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq >/dev/null 2>&1 || true
    apt-get install -y -qq python3-venv python3-pip >/dev/null 2>&1 \
      || die "安装 python3-venv 失败，请手动执行：sudo apt install -y python3-venv python3-pip"
  else
    die "未找到 apt-get，请手动安装 python3-venv"
  fi
fi
info "venv 可用"

HAS_SYSTEMD=0
if [ "$USE_SYSTEMD" = "auto" ]; then
  if command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
    HAS_SYSTEMD=1
  fi
fi
[ "$HAS_SYSTEMD" = "1" ] && info "检测到 systemd" || warn "未检测到 systemd，将以守护进程方式运行"

# ---------- 1. 创建用户与目录 ----------
step "1/7 创建运行用户与目录"
if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --home-dir "$DATA_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
  info "已创建系统用户 $SERVICE_USER"
else
  info "用户 $SERVICE_USER 已存在"
fi

mkdir -p "$INSTALL_DIR" "$DATA_DIR/data/results" "$DATA_DIR/reports" "$LOG_DIR"
info "已创建目录：$INSTALL_DIR · $DATA_DIR · $LOG_DIR"

mkdir -p "$INSTALL_DIR/app/backend" "$INSTALL_DIR/app/frontend"
cp -f "$SRC_DIR"/app/backend/*.py   "$INSTALL_DIR/app/backend/"
cp -f "$SRC_DIR"/app/frontend/*.html "$INSTALL_DIR/app/frontend/"
rm -rf "$INSTALL_DIR/references"
cp -R "$SRC_DIR/references" "$INSTALL_DIR/references"
rm -rf "$INSTALL_DIR"/app/backend/__pycache__
info "已部署程序与知识库到 $INSTALL_DIR"

# ---------- 2. Python 虚拟环境 ----------
step "2/7 创建虚拟环境并安装依赖"
rm -rf "$INSTALL_DIR/venv"
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/python" -m pip install --upgrade pip -q >/dev/null 2>&1 || true

WHEELS="$SRC_DIR/wheels"
HAVE_WHEELS=0
[ -d "$WHEELS" ] && [ -n "$(ls -A "$WHEELS" 2>/dev/null)" ] && HAVE_WHEELS=1

if [ "$PIP_MODE" = "offline" ] || { [ "$PIP_MODE" = "auto" ] && [ "$HAVE_WHEELS" = "1" ]; }; then
  if [ "$HAVE_WHEELS" = "1" ]; then
    "$INSTALL_DIR/venv/bin/pip" install --no-index --find-links "$WHEELS" \
        -r "$INSTALL_DIR/requirements.txt" -q \
      && info "依赖安装完成（离线 wheel）" \
      || die "离线依赖安装失败，可改用：sudo bash install.sh --online"
  else
    die "指定了 --offline 但安装包内没有 wheels/ 目录"
  fi
else
  "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" -q \
    && info "依赖安装完成（联网）" \
    || die "联网安装依赖失败，请检查网络或改用内置 wheel 离线安装"
fi
cp -f "$SRC_DIR/requirements.txt" "$INSTALL_DIR/requirements.txt"
# 版权与许可文件随程序一起落地（CC BY-NC 4.0 要求许可声明随副本分发）
for f in LICENSE.txt NOTICE.md README.md; do
  [ -f "$SRC_DIR/$f" ] && cp -f "$SRC_DIR/$f" "$INSTALL_DIR/$f"
done

# ---------- 3. 配置文件 ----------
step "3/7 写入配置 /etc/eye-agent.env"
cat > /etc/eye-agent.env <<EOF
# 眼健康自查助手运行配置（修改后执行：sudo systemctl restart eye-agent）
EYE_HOST=${EYE_HOST}
EYE_PORT=${EYE_PORT}
EYE_LIB_DIR=${INSTALL_DIR}/references
EYE_DATA_DIR=${DATA_DIR}/data
EYE_REPORT_DIR=${DATA_DIR}/reports
EYE_FRONTEND=${INSTALL_DIR}/app/frontend
EOF
chmod 0644 /etc/eye-agent.env
info "监听 ${EYE_HOST}:${EYE_PORT}"

# ---------- 4. 权限 ----------
step "4/7 设置权限"
chown -R "$SERVICE_USER":"$SERVICE_USER" "$DATA_DIR" "$LOG_DIR"
chown -R root:"$SERVICE_USER" "$INSTALL_DIR"
chmod -R 0750 "$DATA_DIR"
# 关键：venv 在 umask 077 的机器上会建成 700（属主 root），运行用户进不去 →
#      nohup 启动报 "Permission denied"。这里显式把整棵安装树修成可读可执行：
#      目录 755、普通文件 644，venv/bin 下的可执行体保持 755
#      注意：全程用 find -type f/-type d，不直接 chmod 符号链接，
#            否则会跟随到 /usr/bin/python3 去改系统文件
find "$INSTALL_DIR" -type d -exec chmod 0755 {} +
find "$INSTALL_DIR" -type f -not -path "*/venv/bin/*" -exec chmod 0644 {} +
[ -d "$INSTALL_DIR/venv/bin" ] && find "$INSTALL_DIR/venv/bin" -type f -exec chmod 0755 {} +

touch "$LOG_DIR/access.log" "$LOG_DIR/error.log"
chown "$SERVICE_USER":"$SERVICE_USER" "$LOG_DIR/access.log" "$LOG_DIR/error.log"
info "数据目录归属 $SERVICE_USER（仅服务用户可读写）；安装树权限已归一为 755/644"

# ---------- 5. 安装前自检 ----------
step "5/7 启动前自检"
EYE_LIB_DIR="$INSTALL_DIR/references" \
EYE_DATA_DIR="$DATA_DIR/data" \
EYE_REPORT_DIR="$DATA_DIR/reports" \
EYE_FRONTEND="$INSTALL_DIR/app/frontend" \
APP_BACKEND="$INSTALL_DIR/app/backend" \
  "$INSTALL_DIR/venv/bin/python" - <<'PY'
import sys, os
sys.path.insert(0, os.environ["APP_BACKEND"])
from tcm_lib import LIB
s = LIB.stats()
assert s["paragraphs"] > 500, f"知识库索引异常：{s}"
print("知识库段落数:", s["paragraphs"], "| 库路径:", s["lib"])
import app as application
print("应用模块加载成功，路由数:", len(application.app.routes))
PY
info "自检通过"

# ---------- 6. 注册服务 ----------
step "6/7 注册并启动服务"
# 统一启动器：自动加载 /etc/eye-agent.env 后 exec uvicorn
# systemd 与「无 systemd 进程模式」共用它 —— 避免 su 切换用户时环境变量丢失
cat > "$INSTALL_DIR/start.sh" <<EOF
#!/usr/bin/env bash
# 眼健康自查助手启动器（供 systemd / 手动启动共用，自动读取 /etc/eye-agent.env）
set -euo pipefail
if [ -f /etc/eye-agent.env ]; then set -a; . /etc/eye-agent.env; set +a; fi
cd "${INSTALL_DIR}/app/backend"
exec "${INSTALL_DIR}/venv/bin/python" -m uvicorn app:app \\
     --host "\${EYE_HOST:-0.0.0.0}" --port "\${EYE_PORT:-8765}" --log-level warning
EOF
chmod 0755 "$INSTALL_DIR/start.sh"

# 管理命令：按有无 systemd 生成两版（无 systemd 环境用 systemctl 会报 command not found）
write_ctl_systemd() {
cat <<EOF
#!/usr/bin/env bash
# 眼健康自查助手管理命令（systemd 版）
set -euo pipefail
ENV_FILE=/etc/eye-agent.env
SVC=eye-agent
INST=${INSTALL_DIR}
LOG=${LOG_DIR}
DATA=${DATA_DIR}
PORT=\$(grep -E '^EYE_PORT=' "\$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo 8765)
case "\${1:-}" in
  start)   systemctl start \$SVC;  echo "已启动" ;;
  stop)    systemctl stop \$SVC;   echo "已停止" ;;
  restart) systemctl restart \$SVC; echo "已重启" ;;
  status)  systemctl status \$SVC --no-pager ;;
  enable)  systemctl enable \$SVC  >/dev/null 2>&1; echo "已设为开机自启" ;;
  disable) systemctl disable \$SVC >/dev/null 2>&1; echo "已取消开机自启" ;;
  logs)    tail -n "\${2:-80}" -f "\$LOG/error.log" ;;
  url)     IP=\$(hostname -I 2>/dev/null | awk '{print \$1}'); echo "http://\${IP:-\$(hostname)}:\$PORT" ;;
  env)     cat "\$ENV_FILE" ;;
  health)  (command -v curl >/dev/null && curl -fsS "http://127.0.0.1:\$PORT/api/health" || \\
            "\$INST/venv/bin/python" -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:\$PORT/api/health',timeout=3).read().decode())"); echo ;;
  *)
    cat <<'U'
用法：eye-agent {start|stop|restart|status|enable|disable|logs|url|env|health}
U
    ;;
esac
EOF
}

write_ctl_nosystemd() {
cat <<EOF
#!/usr/bin/env bash
# 眼健康自查助手管理命令（无 systemd 版：直接管理后台进程）
set -euo pipefail
ENV_FILE=/etc/eye-agent.env
INST=${INSTALL_DIR}
LOG=${LOG_DIR}
DATA=${DATA_DIR}
USER=${SERVICE_USER}
PIDFILE=\$DATA/eye-agent.pid
PORT=\$(grep -E '^EYE_PORT=' "\$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo 8765)
match() { pgrep -f "uvicorn app:app" 2>/dev/null || true; }
case "\${1:-}" in
  start)
    if [ -n "\$(match)" ]; then echo "已在运行（PID: \$(match | tr '\\n' ' ')）"; exit 0; fi
    mkdir -p "\$DATA"
    su -s /bin/bash "\$USER" -c "cd / && setsid nohup \$INST/start.sh >> \$LOG/access.log 2>> \$LOG/error.log < /dev/null &" 2>/dev/null || \\
    su -s /bin/bash "\$USER" -c "cd / && nohup \$INST/start.sh >> \$LOG/access.log 2>> \$LOG/error.log < /dev/null &"
    sleep 2
    PID=\$(match | head -1 || true)
    if [ -n "\$PID" ]; then echo "\$PID" > "\$PIDFILE"; echo "已启动（PID: \$PID）"; else
      echo "启动失败，请查看：tail -n 50 \$LOG/error.log"; exit 1; fi ;;
  stop)
    PIDS=\$(match)
    [ -n "\$PIDS" ] || { echo "未在运行"; exit 0; }
    kill \$PIDS 2>/dev/null || true
    for i in 1 2 3 4 5 6 7 8 9 10; do [ -z "\$(match)" ] && break; sleep 1; done
    rm -f "\$PIDFILE"; echo "已停止" ;;
  restart) "\$0" stop; sleep 1; "\$0" start ;;
  status)
    PIDS=\$(match)
    if [ -n "\$PIDS" ]; then echo "运行中，PID: \$(echo \$PIDS | tr '\\n' ' ')"; \\
      echo "地址：http://127.0.0.1:\$PORT"; else echo "未运行（启动：sudo eye-agent start）"; fi ;;
  enable)
    if command -v crontab >/dev/null 2>&1; then
      ( crontab -l 2>/dev/null | grep -v 'eye-agent/start.sh' ; echo "@reboot sleep 5 && \$INST/start.sh >> \$LOG/access.log 2>> \$LOG/error.log" ) | crontab -
      echo "已写入 crontab @reboot（开机自启）"
    else
      echo "未找到 crontab，请自行把 \$INST/start.sh 加入开机脚本"; fi ;;
  disable)
    if command -v crontab >/dev/null 2>&1; then
      crontab -l 2>/dev/null | grep -v 'eye-agent/start.sh' | crontab - 2>/dev/null || true
      echo "已取消开机自启"; else echo "未找到 crontab"; fi ;;
  logs)  tail -n "\${2:-80}" -f "\$LOG/error.log" ;;
  url)   IP=\$(hostname -I 2>/dev/null | awk '{print \$1}'); echo "http://\${IP:-\$(hostname)}:\$PORT" ;;
  env)   cat "\$ENV_FILE" ;;
  health)
    (command -v curl >/dev/null && curl -fsS "http://127.0.0.1:\$PORT/api/health" || \\
     "\$INST/venv/bin/python" -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:\$PORT/api/health',timeout=3).read().decode())"); echo ;;
  *)
    cat <<'U'
用法：eye-agent {start|stop|restart|status|enable|disable|logs|url|env|health}
  当前环境无 systemd，服务以后台进程方式管理（开机自启用 crontab @reboot）
U
    ;;
esac
EOF
}

if [ "$HAS_SYSTEMD" = "1" ]; then
  write_ctl_systemd > /usr/local/bin/eye-agent
else
  write_ctl_nosystemd > /usr/local/bin/eye-agent
fi
chmod 0755 /usr/local/bin/eye-agent
bash -n /usr/local/bin/eye-agent || die "管理脚本生成异常"

if [ "$HAS_SYSTEMD" = "1" ]; then
  sed -e "s|/opt/eye-agent|${INSTALL_DIR}|g" \
      -e "s|/var/log/eye-agent|${LOG_DIR}|g" \
      -e "s|/var/lib/eye-agent|${DATA_DIR}|g" \
      -e "s|^User=.*|User=${SERVICE_USER}|" \
      -e "s|^Group=.*|Group=${SERVICE_USER}|" \
      -e "s|\\\${EYE_HOST}|${EYE_HOST}|g" \
      -e "s|\\\${EYE_PORT}|${EYE_PORT}|g" \
      "$SRC_DIR/systemd/eye-agent.service" > /etc/systemd/system/eye-agent.service
  chmod 0644 /etc/systemd/system/eye-agent.service
  systemctl daemon-reload
  systemctl enable eye-agent >/dev/null 2>&1 || true
  systemctl restart eye-agent
  info "systemd 服务已注册并设为开机自启"
else
  sed -e "s|/opt/eye-agent|${INSTALL_DIR}|g" -e "s|^User=.*|User=${SERVICE_USER}|" \
      "$SRC_DIR/systemd/eye-agent.service" > "$INSTALL_DIR/eye-agent.service"
  # 无 systemd（容器 / WSL）：用统一启动器后台拉起（start.sh 会自行加载 /etc/eye-agent.env）
  /usr/local/bin/eye-agent start || true
  warn "环境无 systemd，已以后台进程方式启动；管理命令：sudo eye-agent start|stop|restart|status|logs"
fi

# ---------- 7. 健康检查 ----------
step "7/7 健康检查"
sleep 2
HEALTH=""
for i in $(seq 1 15); do
  if command -v curl >/dev/null 2>&1; then
    HEALTH=$(curl -fsS "http://127.0.0.1:${EYE_PORT}/api/health" 2>/dev/null || true)
  else
    HEALTH=$("$INSTALL_DIR/venv/bin/python" - <<PY
import urllib.request,json
try:
    print(urllib.request.urlopen("http://127.0.0.1:${EYE_PORT}/api/health",timeout=3).read().decode()[:200])
except Exception:
    print("")
PY
)
  fi
  [ -n "$HEALTH" ] && break
  sleep 1
done

if [ -z "$HEALTH" ]; then
  err "服务未就绪。错误日志末尾："
  echo "--------------------------------------------------------------"
  tail -n 30 "$LOG_DIR/error.log" 2>/dev/null || echo "（无 error.log）"
  echo "--------------------------------------------------------------"
  err "排查：① 端口 ${EYE_PORT} 是否被占用（ss -lntp | grep ${EYE_PORT}）"
  err "      ② 手动启动看报错：sudo ${INSTALL_DIR}/start.sh"
  err "      ③ 服务用户权限：sudo -u ${SERVICE_USER} ${INSTALL_DIR}/venv/bin/python -V"
  exit 1
fi
info "服务已就绪：$HEALTH"

IPADDR=$(hostname -I 2>/dev/null | awk '{print $1}')
[ -z "$IPADDR" ] && IPADDR="<服务器IP>"

cat <<EOF

${C_B}════════ 安装完成 ════════${C_0}
  本机访问：  http://127.0.0.1:${EYE_PORT}
  局域网访问：http://${IPADDR}:${EYE_PORT}
  管理命令：  eye-agent {start|stop|restart|status|logs|url|health}
  数据目录：  ${DATA_DIR}（报告与档案）
  日志文件：  ${LOG_DIR}/error.log
  配置文件：  /etc/eye-agent.env（改端口后需 systemctl restart eye-agent）

EOF
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "^Status: active"; then
  warn "检测到 ufw 已启用，若需局域网访问请放行端口：sudo ufw allow ${EYE_PORT}/tcp"
fi
warn "本工具为中医学习参考，不构成诊断；急症（视力骤降、眼胀痛伴头痛呕吐、化学伤等）请立即就医。"
