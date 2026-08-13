# HTTP server，精简自 AnkiConnect 的 web.py（FooSoft/anki-connect）。
#
# 为什么用非阻塞 socket + QTimer 轮询，而不开工作线程：
#   Anki 是 Qt GUI，数据库和调度操作必须在主线程。AnkiConnect 的解法是不开
#   工作线程——socket 设非阻塞，QTimer 每 25ms 回调一次推进 accept/recv，
#   handler 天然跑在主线程（QTimer 回调里）。这样 mw.col 操作绝对安全。
#   代价：慢操作（fsrsApply 可能几十秒）会冻结 GUI——这是已知取舍，Anki
#   原生 Optimize 时 GUI 也近冻结。要非阻塞得改 taskman 异步，但那样拿不到
#   同步 HTTP 返回，MVP 不做。

import json
import socket

from aqt.qt import QTimer

HOST = "127.0.0.1"          # 只听本地，不对外
POLL_INTERVAL_MS = 25
RECV_CHUNK = 65536


class WebClient:
    """单条 HTTP 连接：非阻塞 recv，凑齐一个完整请求后交给 handler。
    采用 Connection: close 语义——处理完一个请求即关闭，简单可靠（curl 每次新连）。"""

    def __init__(self, sock, handler):
        self.sock = sock
        self.handler = handler  # handler(req_dict) -> result_obj（异常会被上层捕获）
        self.buf = b""

    def advance(self):
        # 1) 非阻塞读取，尽量累积到 buffer
        try:
            while True:
                chunk = self.sock.recv(RECV_CHUNK)
                if not chunk:
                    return False  # 对端关闭
                self.buf += chunk
        except BlockingIOError:
            pass  # 缓冲区暂空，正常

        # 2) 检查是否收齐一个完整请求
        sep = self.buf.find(b"\r\n\r\n")
        if sep < 0:
            return True  # header 还没结束，等下次轮询
        header = self.buf[:sep]
        body_start = sep + 4

        content_length = 0
        for line in header.split(b"\r\n"):
            if line.lower().startswith(b"content-length:"):
                try:
                    content_length = int(line.split(b":", 1)[1].strip())
                except ValueError:
                    content_length = 0
                break

        if len(self.buf) - body_start < content_length:
            return True  # body 还没收完

        body = self.buf[body_start:body_start + content_length]
        method = header.split(b"\r\n", 1)[0].split(b" ")[0]

        # 3) 处理并回复
        if method == b"OPTIONS":
            # CORS 预检
            self._send(self._response(b""))
        else:
            try:
                req = json.loads(body.decode("utf-8")) if body else {}
                result = self.handler(req)
                payload = {"result": result, "error": None}
            except Exception as e:
                # 任何异常都包成 error 返回，不让插件崩
                payload = {"result": None, "error": str(e)}
            self._send(self._response(json.dumps(payload).encode("utf-8")))

        return False  # Connection: close，处理完就关

    def _response(self, body):
        headers = [
            "HTTP/1.1 200 OK",
            "Content-Type: application/json; charset=utf-8",
            f"Content-Length: {len(body)}",
            "Access-Control-Allow-Origin: *",
            "Access-Control-Allow-Headers: Content-Type",
            "Access-Control-Allow-Methods: POST, OPTIONS",
            "Connection: close",
        ]
        return ("\r\n".join(headers) + "\r\n\r\n").encode("utf-8") + body

    def _send(self, data):
        # 响应通常很小（FSRS 结果几百字节），临时切回 blocking 一次发完最稳。
        try:
            self.sock.setblocking(True)
            self.sock.sendall(data)
        except (BlockingIOError, BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            try:
                self.sock.setblocking(False)
            except OSError:
                pass


class WebServer:
    def __init__(self, handler, host=HOST, port=8766):
        self.handler = handler
        self.host = host
        self.port = port
        self.sock = None
        self.clients = []
        self.timer = None

    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setblocking(False)
        self.sock.bind((self.host, self.port))
        self.sock.listen(5)
        self.timer = QTimer()
        self.timer.timeout.connect(self._advance)
        self.timer.start(POLL_INTERVAL_MS)

    def _advance(self):
        if self.sock is None:
            return
        # 非阻塞 accept 所有待连接
        try:
            while True:
                client_sock, _ = self.sock.accept()
                client_sock.setblocking(False)
                self.clients.append(WebClient(client_sock, self.handler))
        except BlockingIOError:
            pass
        # 推进每个 client，踢掉已关闭的
        self.clients = [c for c in self.clients if c.advance()]
