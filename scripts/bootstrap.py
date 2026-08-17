#!/usr/bin/env python3
# anki-tutor bootstrap —— AnkiConnect + fsrs_bridge 的安装 / 升级 / 体检 / 自愈
#
# 流程：探测 → 决策 → （--dry-run 只打印）→ 执行 → 冷/热装指引 → 验证
#
# 红线：
#   - 幂等：重复跑安全；已装且为最新则零操作
#   - 只写目标 base 的 addons21/，绝不碰 profiles / collection
#   - 探测全部从目标 base 派生（端口读目标 base 里插件的 config.json），
#     不查全局机器状态——沙箱与生产同一套逻辑
#
# 退出码：0 = 就绪（含 dry-run）；1 = 已装好但需用户动作（开/重启 Anki）；2 = 失败
#
# 用法：
#   python bootstrap.py --dry-run                 # 体检 + 打印将要做什么
#   python bootstrap.py                           # 自动探测 base，缺啥装啥
#   python bootstrap.py --wait 60                 # 装完等 Anki 起来（探活轮询）
#   python bootstrap.py --base <dir> --ankiconnect-port 18765 --bridge-port 18766   # 沙箱

import argparse
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.request
import zipfile

ANKICONNECT_ID = "2055492159"
# p 参数是 AnkiWeb 的分支选择器：457 = 当前现代分支（2026-08-17 实测与内置快照逐字节
# 一致）。裸 URL 返回 404；只带 v=2.1 不带 p 会拿到缺 edit.py 的旧分支——都别用。
ANKICONNECT_URL = f"https://ankiweb.net/shared/download/{ANKICONNECT_ID}?v=2.1&p=457"
BRIDGE_DIR = "fsrs_bridge"
DEFAULT_AC_PORT = 8765
DEFAULT_BRIDGE_PORT = 8766

EXIT_READY, EXIT_ACTION, EXIT_ERROR = 0, 1, 2


def _setup_console():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def log(msg):
    print(msg, flush=True)


# ---------- 通用小工具 ----------

def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=4, ensure_ascii=False)


def merge_json(path, patch):
    obj = read_json(path) or {}
    obj.update(patch)
    write_json(path, obj)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def py_tree_hash(root):
    """目录下所有 .py 的 {相对路径: hash}——判断插件版本是否与源一致"""
    entries = {}
    if not os.path.isdir(root):
        return None
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in filenames:
            if fn.endswith(".py"):
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, root).replace("\\", "/")
                entries[rel] = sha256(full)
    return entries


def http_post(url, payload, timeout):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def probe_port(port):
    """探活：HTTP 服务肯回 JSON（哪怕 error 字段）就算活着。用 127.0.0.1，避开 IPv6 localhost 歧义。"""
    try:
        r = http_post(f"http://127.0.0.1:{port}", {"action": "version", "version": 6}, 1.5)
        return True, r
    except Exception:
        return False, None


# ---------- 探测 ----------

def base_candidates():
    out = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        out.append(os.path.join(appdata, "Anki2"))
    home = os.path.expanduser("~")
    out += [
        os.path.join(home, "Library", "Application Support", "Anki2"),
        os.path.join(home, ".local", "share", "Anki2"),
        os.path.join(home, ".var", "app", "net.ankiweb.Anki", "data", "Anki2"),  # Flatpak
    ]
    return out


def detect_base():
    best, best_score = None, -1
    for p in base_candidates():
        if not os.path.isdir(p):
            continue
        score = 0
        if os.path.isdir(os.path.join(p, "addons21")):
            score = 1
        if os.path.isdir(os.path.join(p, "addons21", ANKICONNECT_ID)):
            score = 2  # 有 AnkiConnect 的多半是用户真实在用的 base
        if any(os.path.isfile(os.path.join(p, n)) for n in ("prefs21.db", "prefs.db")):
            score += 1
        if score > best_score:
            best, best_score = p, score
    return best


def is_anki_base(path):
    return os.path.isdir(os.path.join(path, "addons21")) or any(
        os.path.isfile(os.path.join(path, n)) for n in ("prefs21.db", "prefs.db")
    )


def find_anki_exe():
    """尽力定位 anki.exe（只用于报告，不影响安装）。找不到返回 None。"""
    home = os.path.expanduser("~")
    cands = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Anki\anki.exe"),
        r"C:\Program Files\Anki\anki.exe",
        os.path.join(home, "Library", "Application Support", "Anki2"),  # placeholder 排错用
    ]
    cands[2] = "/Applications/Anki.app/Contents/MacOS/anki"
    cands += ["/usr/local/bin/anki", "/usr/bin/anki"]
    for c in cands:
        if os.path.isfile(c):
            return c
    return shutil.which("anki")


def resolve_ports(args, ac_dir, bridge_dir):
    """端口优先级：CLI 参数 > 目标 base 里插件 config.json > 默认值。"""
    ac_port = args.ankiconnect_port
    if ac_port is None:
        cfg = read_json(os.path.join(ac_dir, "config.json")) if ac_dir else None
        ac_port = (cfg or {}).get("webBindPort", DEFAULT_AC_PORT)
    br_port = args.bridge_port
    if br_port is None:
        cfg = read_json(os.path.join(bridge_dir, "config.json")) if bridge_dir else None
        br_port = (cfg or {}).get("port", DEFAULT_BRIDGE_PORT)
    return int(ac_port), int(br_port)


# ---------- 计划与执行 ----------

def build_plan(args, ac_dir, bridge_dir, bridge_src, ac_bundled):
    ops = []

    # --- AnkiConnect：只管"有没有"，不管版本 ---
    if not os.path.isfile(os.path.join(ac_dir, "__init__.py")):
        # 来源顺序：--ankiconnect-src > skill 内置快照 > ankiweb 下载兜底
        src, kind, src_desc = None, "download", f"ankiweb 下载 {ANKICONNECT_URL}"
        if args.ankiconnect_src:
            if os.path.isdir(args.ankiconnect_src):
                src, kind, src_desc = args.ankiconnect_src, "dir", args.ankiconnect_src
            elif os.path.isfile(args.ankiconnect_src):
                src, kind, src_desc = args.ankiconnect_src, "zip", args.ankiconnect_src
            else:
                return None, f"--ankiconnect-src 不存在：{args.ankiconnect_src}"
        elif os.path.isfile(os.path.join(ac_bundled, "__init__.py")):
            src, kind, src_desc = ac_bundled, "dir", "skill 内置快照"
        ops.append({"kind": "install_ankiconnect", "dst": ac_dir, "src": src,
                    "src_kind": kind, "desc": f"安装 AnkiConnect（来源：{src_desc}）"})
        now = int(time.time())
        ops.append({"kind": "write_json", "path": os.path.join(ac_dir, "meta.json"),
                    "obj": {"name": "AnkiConnect", "mod": now, "installed_at": now},
                    "desc": "预写 meta.json（避免缺省值触发每日更新提示）"})
    if args.ankiconnect_port:
        cur = (read_json(os.path.join(ac_dir, "config.json")) or {}).get("webBindPort")
        if cur != args.ankiconnect_port:
            ops.append({"kind": "merge_json", "path": os.path.join(ac_dir, "config.json"),
                        "patch": {"webBindPort": args.ankiconnect_port},
                        "desc": f"AnkiConnect 端口预写为 {args.ankiconnect_port}"})

    # --- fsrs_bridge：hash 比对决定 装 / 升级 / 跳过 ---
    if not (os.path.isdir(bridge_src) and os.path.isfile(os.path.join(bridge_src, "__init__.py"))):
        return None, f"fsrs_bridge 源目录无效：{bridge_src}"
    installed = os.path.isfile(os.path.join(bridge_dir, "__init__.py"))
    current = installed and py_tree_hash(bridge_src) == py_tree_hash(bridge_dir)
    if not installed or not current:
        verb = "升级" if installed else "安装"
        ops.append({"kind": "install_tree", "src": bridge_src, "dst": bridge_dir,
                    "keep": ["config.json", "bridge-status.json", "bridge-debug.log"],
                    "desc": f"{verb} fsrs_bridge -> {bridge_dir}"})
    if args.bridge_port:
        cur = (read_json(os.path.join(bridge_dir, "config.json")) or {}).get("port")
        if cur != args.bridge_port:
            ops.append({"kind": "merge_json", "path": os.path.join(bridge_dir, "config.json"),
                        "patch": {"port": args.bridge_port},
                        "desc": f"fsrs_bridge 端口预写为 {args.bridge_port}"})
    return ops, None


def _copy_tree(src, dst, keep=()):
    """覆盖式复制目录；keep 里的文件（用户 config / 状态自报）先暂存再还原。"""
    kept = {}
    if os.path.isdir(dst):
        for name in keep:
            p = os.path.join(dst, name)
            if os.path.isfile(p):
                fd, tmp = tempfile.mkstemp()
                os.close(fd)
                shutil.copy2(p, tmp)
                kept[name] = tmp
        shutil.rmtree(dst)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
    for name, tmp in kept.items():
        shutil.copy2(tmp, os.path.join(dst, name))
        os.remove(tmp)


def _install_ankiconnect(op):
    dst, src, kind = op["dst"], op["src"], op.get("src_kind", "download")
    if kind == "dir":
        _copy_tree(src, dst)
        return
    data = None
    if kind == "zip":
        with open(src, "rb") as f:
            data = f.read()
    else:
        log(f"  下载 {ANKICONNECT_URL} ...")
        with urllib.request.urlopen(ANKICONNECT_URL, timeout=30) as r:
            data = r.read()
    if not data[:2] == b"PK":
        raise RuntimeError("AnkiConnect 下载内容不是 zip（来源异常），中止")
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        os.makedirs(dst, exist_ok=True)
        z.extractall(dst)


def execute(ops, addons21):
    real_addons = os.path.realpath(addons21)
    for op in ops:
        log(f"  • {op['desc']}")
        # 保险：一切写操作必须落在目标 addons21 内
        target = op.get("dst") or op.get("path")
        if target and not os.path.realpath(target).startswith(real_addons + os.sep):
            raise RuntimeError(f"拒绝写入 addons21 之外：{target}")
        if op["kind"] == "install_ankiconnect":
            _install_ankiconnect(op)
        elif op["kind"] == "install_tree":
            _copy_tree(op["src"], op["dst"], keep=op.get("keep", ()))
        elif op["kind"] == "write_json":
            write_json(op["path"], op["obj"])
        elif op["kind"] == "merge_json":
            merge_json(op["path"], op["patch"])
        else:
            raise RuntimeError(f"未知操作：{op['kind']}")


# ---------- 主流程 ----------

def smoke(ac_port, br_port):
    """就绪后的冒烟：AnkiConnect deckNames + bridge fsrsStatus（只读）。"""
    notes = []
    try:
        r = http_post(f"http://127.0.0.1:{ac_port}",
                      {"action": "deckNames", "version": 6}, 5)
        if r.get("error"):
            notes.append(f"AnkiConnect 冒烟返回 error: {r['error']}")
        else:
            notes.append(f"deckNames OK（{len(r.get('result') or [])} 个牌组）")
    except Exception as e:
        notes.append(f"AnkiConnect 冒烟失败: {e}")
    try:
        r = http_post(f"http://127.0.0.1:{br_port}",
                      {"action": "fsrsStatus", "version": 6, "params": {}}, 5)
        if r.get("error"):
            notes.append(f"fsrs_bridge 冒烟返回 error: {r['error']}")
        else:
            notes.append(f"fsrsStatus OK（ankiVersion {r.get('result', {}).get('ankiVersion')}）")
    except Exception as e:
        notes.append(f"fsrs_bridge 冒烟失败: {e}")
    return notes


def main():
    _setup_console()
    ap = argparse.ArgumentParser(description="anki-tutor 环境安装/自愈")
    ap.add_argument("--base", help="Anki 数据目录（缺省自动探测；沙箱测试用）")
    ap.add_argument("--dry-run", action="store_true", help="只打印将执行的操作，不写任何文件")
    ap.add_argument("--ankiconnect-port", type=int, help="AnkiConnect 端口预写（默认不动）")
    ap.add_argument("--bridge-port", type=int, help="fsrs_bridge 端口预写（默认不动）")
    ap.add_argument("--ankiconnect-src", help="AnkiConnect 本地来源（目录或 zip），缺省从 ankiweb 下载")
    ap.add_argument("--bridge-src", help="fsrs_bridge 源目录（默认 skill 自带 plugin/fsrs_bridge）")
    ap.add_argument("--wait", type=int, default=0, help="装完后等待 Anki 就绪的秒数（探活轮询）")
    ap.add_argument("--json", action="store_true", help="最后输出机器可读的 JSON 摘要")
    args = ap.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    bridge_src = args.bridge_src or os.path.normpath(
        os.path.join(script_dir, "..", "plugin", BRIDGE_DIR))
    ac_bundled = os.path.normpath(
        os.path.join(script_dir, "..", "plugin", "ankiconnect"))

    # ---- 探测 ----
    base = args.base or detect_base()
    if not base:
        log("✗ 找不到 Anki 数据目录（标准位置都没有）。用 --base 显式指定。")
        return EXIT_ERROR
    base = os.path.abspath(base)
    if not is_anki_base(base):
        log(f"✗ {base} 不像 Anki 数据目录（无 addons21 / prefs21.db）。")
        return EXIT_ERROR
    addons21 = os.path.join(base, "addons21")
    ac_dir = os.path.join(addons21, ANKICONNECT_ID)
    bridge_dir = os.path.join(addons21, BRIDGE_DIR)
    ac_port, br_port = resolve_ports(args, ac_dir, bridge_dir)
    ac_alive, _ = probe_port(ac_port)
    br_alive, _ = probe_port(br_port)
    bridge_status = read_json(os.path.join(bridge_dir, "bridge-status.json"))
    exe = find_anki_exe()

    log("── 环境状态 " + "─" * 40)
    log(f"base        : {base}")
    log(f"anki.exe    : {exe or '未找到（不影响安装）'}")
    log(f"AnkiConnect : {'已装' if os.path.isfile(os.path.join(ac_dir, '__init__.py')) else '未装'}"
        f" | 端口 {ac_port} | {'● 在线' if ac_alive else '○ 无响应'}")
    cur = (os.path.isfile(os.path.join(bridge_dir, "__init__.py"))
           and py_tree_hash(bridge_src) == py_tree_hash(bridge_dir))
    log(f"fsrs_bridge : {'已装(最新)' if cur else ('已装(旧版)' if os.path.isfile(os.path.join(bridge_dir, '__init__.py')) else '未装')}"
        f" | 端口 {br_port} | {'● 在线' if br_alive else '○ 无响应'}")
    if bridge_status:
        log(f"bridge 自报 : started={bridge_status.get('started')} port={bridge_status.get('port')}"
            f" error={bridge_status.get('error')}")

    # ---- 决策 ----
    ops, err = build_plan(args, ac_dir, bridge_dir, bridge_src, ac_bundled)
    if err:
        log(f"✗ {err}")
        return EXIT_ERROR
    if not ops:
        log("✓ 无需任何操作：两个组件均已安装且为最新。")
        if ac_alive and br_alive:
            for n in smoke(ac_port, br_port):
                log(f"  - {n}")
            log("✓ 一切就绪：两个服务均在线。")
            if args.json:
                log("JSON " + json.dumps({"result": "ready"}, ensure_ascii=False))
            return EXIT_READY
        log("→ Anki 当前未运行（或插件未随启动）。打开 Anki 即可使用。")
        if args.json:
            log("JSON " + json.dumps({"result": "installed_not_running"}, ensure_ascii=False))
        return EXIT_ACTION

    # ---- 执行 ----
    if args.dry_run:
        log("── 计划执行以下操作（dry-run，未写入） " + "─" * 14)
        for op in ops:
            log(f"  • {op['desc']}")
            if op["kind"] == "write_json":
                log(f"      内容: {json.dumps(op['obj'], ensure_ascii=False)}")
        log("dry-run 完成，未写任何文件。")
        if args.json:
            log("JSON " + json.dumps({"result": "dry_run", "ops": len(ops)}, ensure_ascii=False))
        return EXIT_READY

    log("── 执行 " + "─" * 49)
    try:
        execute(ops, addons21)
    except Exception as e:
        log(f"✗ 执行失败：{e}")
        return EXIT_ERROR
    log(f"✓ 完成 {len(ops)} 项操作。")

    # 执行前 Anki 是否在跑。热装时端口活着 ≠ 新代码生效（应答的还是旧实例），
    # 所以执行过操作就不能只凭端口判就绪——冷装等到的启动才保证是新代码。
    was_running = ac_alive
    if args.wait > 0 and not was_running:
        log(f"── 等待服务就绪（最多 {args.wait}s；现在请打开 Anki）")
        deadline = time.time() + args.wait
        while time.time() < deadline:
            ac_alive, _ = probe_port(ac_port)
            br_alive, _ = probe_port(br_port)
            if ac_alive and br_alive:
                break
            time.sleep(1)

    ac_alive, _ = probe_port(ac_port)
    br_alive, _ = probe_port(br_port)
    if not was_running and ac_alive and br_alive:
        for n in smoke(ac_port, br_port):
            log(f"  - {n}")
        log("✓ 一切就绪：两个服务均在线。")
        result, code = "ready", EXIT_READY
    elif was_running:
        log("→ Anki 正在运行，但刚装/升级的插件需重启才能生效：请重启一次 Anki。"
            "重启后可再跑本脚本验证（应显示无需任何操作）。")
        result, code = "needs_restart", EXIT_ACTION
    else:
        log("→ Anki 未运行：下次打开 Anki 即自动生效，无需其他操作。")
        result, code = "needs_open", EXIT_ACTION
    if args.json:
        log("JSON " + json.dumps({"result": result, "ops": len(ops),
                                  "ac_port": ac_port, "bridge_port": br_port}, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
