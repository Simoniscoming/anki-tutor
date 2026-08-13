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

from aqt import gui_hooks

from .web import WebServer
from .handlers import dispatch

PORT = 8766

_server = None


def _on_profile_open():
    # profile_did_open 在 collection 加载后触发一次，此时 mw.col 已就绪，
    # 比模块 import 时机更安全。
    global _server
    if _server is not None:
        return
    _server = WebServer(handler=dispatch, port=PORT)
    try:
        _server.start()
        print(f"[fsrs_bridge] listening on http://127.0.0.1:{PORT}")
    except Exception as e:
        # 端口被占等：打印到 stderr，不崩 Anki
        print(f"[fsrs_bridge] failed to start: {e}")


gui_hooks.profile_did_open.append(_on_profile_open)
