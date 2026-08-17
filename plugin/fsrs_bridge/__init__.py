# fsrs_bridge —— 在 Anki 里开一个本地 HTTP 端口（默认 8766），暴露 FSRS
# optimize / reschedule 能力，补上 AnkiConnect（8765）没转发的缺口。
#
# 线程模型：照搬 AnkiConnect——非阻塞 socket + QTimer 25ms 轮询，所有 handler
# 跑在 Qt 主线程，可直接访问 mw.col，无需 run_on_main。
#
# 安装：把整个 fsrs_bridge 文件夹放到 Anki 的 addons21 目录，重启 Anki。
#   Windows: %APPDATA%\Anki2\addons21\
#   macOS:   ~/Library/Application Support/Anki2/addons21/
#   Linux:   ~/.local/share/Anki2/addons21/
#
# 验证：重启后调 curl -s http://localhost:8766 -d '{"action":"fsrsStatus","version":6}'

import json
import os
import time

_DIR = os.path.dirname(os.path.abspath(__file__))


def _dbg(msg):
    # 诊断日志：Windows GUI 下 print 完全不可见（logs/ 也不收），
    # 加载链条上任何一段的问题，只有落盘才知道卡在哪。
    try:
        with open(os.path.join(_DIR, "bridge-debug.log"), "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except Exception:
        pass


_dbg("=== module import start ===")

from aqt import gui_hooks, mw

from .web import WebServer
from .handlers import dispatch

_dbg("imports ok (aqt / web / handlers)")

DEFAULT_PORT = 8766

_server = None


def _write_status(ok, port, error=None):
    # 状态自报：起没起来、绑没绑上、为什么失败，写进插件目录
    try:
        status = {
            "started": ok,
            "port": port,
            "error": error,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        with open(os.path.join(_DIR, "bridge-status.json"), "w", encoding="utf-8") as f:
            json.dump(status, f, indent=2)
    except Exception as e:
        _dbg(f"_write_status failed: {e!r}")


def _on_profile_open():
    # profile_did_open 在 collection 加载后触发一次，此时 mw.col 已就绪，
    # 比模块 import 时机更安全。
    global _server
    _dbg("profile_did_open fired")
    if _server is not None:
        _dbg("already running, skip")
        return
    port = DEFAULT_PORT
    try:
        # 端口由 config.json 的 "port" 决定：沙箱换口（18766）、生产预置都靠它
        cfg = mw.addonManager.getConfig(__name__) or {}
        _dbg(f"config = {cfg!r}")
        port = int(cfg.get("port", DEFAULT_PORT))
        _server = WebServer(handler=dispatch, port=port)
        _server.start()
        _dbg(f"listening on 127.0.0.1:{port}")
        _write_status(True, port)
    except Exception as e:
        # 端口被占 / config 异常等：不崩 Anki，原因落盘
        _dbg(f"FAILED on port {port}: {e!r}")
        _write_status(False, port, repr(e))


gui_hooks.profile_did_open.append(_on_profile_open)
_dbg("hook registered")
