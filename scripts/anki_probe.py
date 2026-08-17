#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
anki_probe.py —— anki-tutor skill 的只读探测脚本（v1）

设计契约（详见 references/anki-control.md「脚本优先」节）：
- 只读：绝不调用任何写操作 action。带牌组名的调用（cardReviews/getDeckStats 等，
  AnkiConnect 拿到不存在的名字会静默创建空牌组——坑6），牌组名一律先经 resolve_deck
  与 deckNames 返回精确比对，比对不上直接报错退出，绝不透传。
- 中文/查询一律走 HTTP JSON body（urllib），完全不经过 shell，规避引号与编码坑。
- 输出：默认人读摘要；--json 输出机器可读完整数据。
- 退出码：0 成功 / 1 Anki 不可达 / 2 用法错误（含牌组名不存在）/ 3 Anki 返回 error。
- 环境：Python 3.8+，仅标准库。Windows / macOS / Linux 同一份代码。
- 环境变量：ANKI_URL（默认 http://localhost:8765）、ANKI_BRIDGE_URL（默认 8766，可选）。

子命令：
  check                       连通性 + 版本 + 牌组树概览
  shells                      空壳牌组扫描（含创建时间溯源）
  dedup --deck D --query Q    查重候选拉取与字段归一化
  collect --deck D [--days N] 诊断数据采集与指标计算（喂看板模板用）
  selftest [--deck D]         对上游 AnkiConnect 做返回形状探针（schema 漂移检测）
"""

SCHEMA_VERSION = 1

import argparse
import datetime
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request

EXIT_OK, EXIT_CONN, EXIT_USAGE, EXIT_ANKI = 0, 1, 2, 3
ANKI_URL = os.environ.get("ANKI_URL", "http://localhost:8765")
BRIDGE_URL = os.environ.get("ANKI_BRIDGE_URL", "http://localhost:8766")

# 强制 UTF-8 输出（Windows 控制台代码页兜底），不依赖 PYTHONIOENCODING
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 版本闸门：声明支持 3.7+（stdout.reconfigure 与 add_subparsers(required=) 均为 3.7 引入），
# 实测 3.13。更老版本在此报清晰错误快速失败，由 skill 降级为 curl 手工流程。
if sys.version_info < (3, 7):
    sys.stderr.write("需要 Python 3.7+（当前 %d.%d）。请升级，或退回 curl 手工流程"
                     "（references/anki-control.md 模板）。\n" % sys.version_info[:2])
    sys.exit(EXIT_USAGE)


# ---------------------------------------------------------------- HTTP 层

class AnkiDown(Exception):
    pass


def post(url, action, params, timeout=30):
    body = json.dumps({"action": action, "version": 6, "params": params}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            res = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as e:
        raise AnkiDown(str(e))
    if res.get("error") is not None:
        raise RuntimeError("%s: %s" % (action, res["error"]))
    return res.get("result")


def ac(action, **params):
    return post(ANKI_URL, action, params)


# ---------------------------------------------------------------- 通用工具

def resolve_deck(name, deck_names=None):
    """牌组名必须与 deckNames 返回逐字一致（坑6 防御）。不一致 → 报错并列相近候选。"""
    deck_names = deck_names if deck_names is not None else ac("deckNames")
    if name in deck_names:
        return name
    norm = lambda s: re.sub(r"[\s_\-]+", "", s).lower()
    cands = [d for d in deck_names if norm(d) == norm(name)]
    if not cands:
        cands = [d for d in deck_names if name in d or d in name][:6]
    raise SystemExit(_usage_err("牌组名不存在：%r（cardReviews 等接口会静默创建空牌组，已拒绝透传）。相近候选：%s"
                                % (name, "、".join(cands) if cands else "无")))


def subtree_of(deck, deck_names):
    pre = deck + "::"
    return [d for d in deck_names if d == deck or d.startswith(pre)]


def qdeck(deck):
    """Anki 搜索语法里 deck 名一律加引号（坑2：空格/中文）。"""
    return 'deck:"%s"' % deck


def strip_html(s):
    s = re.sub(r"<br\s*/?>", " ", s or "")
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


def excerpt(s, n=80):
    s = strip_html(s)
    return s if len(s) <= n else s[:n] + "…"


def _usage_err(msg):
    sys.stderr.write("[用法错误] %s\n" % msg)
    return EXIT_USAGE


# ---------------------------------------------------------------- check

def cmd_check(args):
    ver = ac("version")
    names = ac("deckNames")
    today = ac("getNumCardsReviewedToday")
    out = {
        "ankiConnectVersion": ver,
        "ankiUrl": ANKI_URL,
        "python": sys.version.split()[0],
        "deckCount": len(names),
        "decks": sorted(names),
        "reviewedToday": today,
    }
    try:
        st = post(BRIDGE_URL, "fsrsStatus", {}, timeout=5)
        out["fsrsBridge"] = st
    except Exception:
        out["fsrsBridge"] = {"available": False}
    if not args.json:
        print("✓ AnkiConnect %s @ %s（今日已复习 %s 次，共 %d 个牌组）"
              % (ver, ANKI_URL, today, len(names)))
        b = out["fsrsBridge"]
        if b.get("available") is False:
            print("✗ fsrs_bridge 不可达（%s）——Tier 3 自动优化将降级为 GUI 指引" % BRIDGE_URL)
        elif b.get("fsrsEnabled") is None:
            print("✓ fsrs_bridge 在线（%s）——全局探测不带牌组上下文，具体牌组的 FSRS 状态用 collect --deck X 查" % BRIDGE_URL)
        else:
            print("✓ fsrs_bridge %s：FSRS=%s v3=%s 距上次优化 %s 天"
                  % (BRIDGE_URL, b.get("fsrsEnabled"), b.get("v3scheduler"), b.get("daysSinceLastOptimize")))
        print("牌组树：")
        for d in sorted(names):
            print("  " + "  " * d.count("::") + d.split("::")[-1] + ("  (%s)" % d if "::" in d else ""))
    else:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    return EXIT_OK


# ---------------------------------------------------------------- shells

def cmd_shells(args):
    names = ac("deckNames")
    stats = ac("getDeckStats", decks=names)  # key=deckId(创建时间戳ms)
    id_by_name = {v.get("name"): k for k, v in stats.items()} if stats else {}
    rows = []
    for d in sorted(names):
        exact = len(ac("findCards", query='deck:"%s" -deck:"%s::*"' % (d, d)) or [])
        tree = len(ac("findCards", query='deck:"%s"' % d) or [])
        did = id_by_name.get(d)
        try:
            created = datetime.datetime.fromtimestamp(int(did) / 1000).strftime("%Y-%m-%d %H:%M") if did else None
        except Exception:
            created = None
        if tree == 0:  # 整棵子树无卡 → 空壳候选（是否为结构性父牌组由人判断）
            rows.append({"deck": d, "cardsInDeck": exact, "cardsInTree": tree,
                         "created": created, "deckId": did})
    if not args.json:
        if not rows:
            print("没有整树无卡的空壳牌组。")
        else:
            print("空壳候选（整棵子树 0 卡）共 %d 个，创建时间可溯源：" % len(rows))
            for r in sorted(rows, key=lambda x: x["created"] or "9"):
                print("  %-20s 创建于 %s  id=%s" % (r["deck"], r["created"] or "?", r["deckId"]))
            if any(r["created"] is None for r in rows):
                print("注：创建时间 ? = getDeckStats 未返回该牌组——常见于内置默认牌组（ID 恒为 1，无时间戳语义）"
                      "或无到期卡的牌组，溯源不适用；内置默认牌组不可删。")
            print("注：仅报告，不删除。清理需用户确认后 deleteDecks cardsToo:true（空壳无数据）。")
    else:
        print(json.dumps({"shellCandidates": rows}, ensure_ascii=False, indent=1))
    return EXIT_OK


# ---------------------------------------------------------------- dedup

FRONT_KEYS = ["Front", "Text", "正面", "文字", "问题", "Question", "Term", "Word"]
BACK_KEYS = ["Back", "Back Extra", "背面", "背面额外", "答案", "Answer", "Definition", "Meaning"]


def pick_field(fields, keys, idx):
    for k in keys:
        if k in fields:
            return k
    ordered = list(fields.keys())
    return ordered[idx] if len(ordered) > idx else (ordered[0] if ordered else None)


def note_row(n, model_fields):
    f = {}
    for k, v in (n.get("fields") or {}).items():
        f[k] = v["value"] if isinstance(v, dict) else (v or "")
    fk = pick_field(f, FRONT_KEYS, 0)
    bk = pick_field(f, BACK_KEYS, 1)
    return {
        "noteId": n.get("noteId"),
        "cardIds": n.get("cards", []),  # AnkiConnect 实测：cardId 整数列表，非对象
        "model": n.get("modelName"),
        "modelFields": model_fields.get(n.get("modelName"), list(f.keys())),
        "tags": n.get("tags", []),
        "frontKey": fk, "backKey": bk,
        "front": excerpt(f.get(fk, ""), 90),
        "back": excerpt(f.get(bk, ""), 90),
    }


def cmd_dedup(args):
    names = ac("deckNames")
    deck = resolve_deck(args.deck, names)
    hits = ac("findNotes", query="%s %s" % (qdeck(deck), args.query)) or []
    cross = None
    if not hits:  # 坑2：空结果必须交叉验证后才可下结论
        cross = ac("findNotes", query=args.query) or []
    rows = []
    if hits:
        # 每个模型查一次字段名（兼容中文自定义字段模型），notesInfo 拉内容
        models = sorted({n.get("modelName") for n in (ac("notesInfo", notes=hits) or [])})
        model_fields = {}
        for m in models:
            try:
                model_fields[m] = ac("modelFieldNames", modelName=m) or []
            except Exception:
                model_fields[m] = []
        rows = [note_row(n, model_fields) for n in (ac("notesInfo", notes=hits) or [])]
        rows.sort(key=lambda r: r["noteId"] or 0)
    if args.json:
        print(json.dumps({"deck": deck, "query": args.query, "matches": len(hits),
                          "crossCheckOutsideDeck": len(cross) if cross is not None else None,
                          "candidates": rows}, ensure_ascii=False, indent=1))
        return EXIT_OK
    print("查重：%s ∩ %r → 命中 %d 张" % (deck, args.query, len(hits)))
    if not hits and cross is not None:
        if cross:
            print("⚠ 本牌组无命中，但【其他牌组】有 %d 张含此关键词——去重前先看这些：" % len(cross))
            info = ac("notesInfo", notes=cross[:10]) or []
            for n in info:
                r = note_row(n, {})
                print("   #%s [%s] %s" % (r["noteId"], r["model"], r["front"][:60]))
        else:
            print("交叉验证（去 deck 限定重查）也无命中 → 判定：无重复。")
    for r in rows[:20]:
        print("  #%s [%s] tags=%s" % (r["noteId"], r["model"], ",".join(r["tags"]) or "-"))
        print("    F(%s): %s" % (r["frontKey"], r["front"]))
        print("    B(%s): %s" % (r["backKey"], r["back"]))
    if len(rows) > 20:
        print("  …另 %d 张省略（--json 看全量）" % (len(rows) - 20))
    print("（脚本只拉候选，像不像、跳不跳过由你和用户判断。）" if rows else "")
    return EXIT_OK


# ---------------------------------------------------------------- collect

K_BY_DR = [(0.96, 18), (0.95, 14), (0.92, 11), (0.90, 9), (0.87, 7.5), (0.85, 6.5), (0.80, 5)]


def k_for_dr(dr):
    for threshold, k in K_BY_DR:
        if dr >= threshold:
            return k
    return 5


def read_intent():
    base = os.environ.get("APPDATA") or os.path.expanduser("~/.local/share")
    for p in (os.path.join(base, "anki-coach", "intent.json"),
              os.path.expanduser("~/.local/share/anki-coach/intent.json")):
        try:
            with open(p, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            continue
    return None


def config_with_fallback(deck, names):
    """deck 无独立配置组时沿 :: 向上找（getDeckConfig 返回 null/False = 继承父级）。"""
    chain = []
    parts = deck.split("::")
    for i in range(len(parts), 0, -1):
        cand = "::".join(parts[:i])
        if cand in names:
            chain.append(cand)
    for cand in chain:
        cfg = ac("getDeckConfig", deck=cand)
        if cfg:
            return cand, cfg
    return None, None


def cmd_collect(args):
    names = ac("deckNames")
    deck = resolve_deck(args.deck, names)
    days = args.days
    start_ms = int((time.time() - days * 86400) * 1000)

    cfg_deck, cfg = config_with_fallback(deck, names)
    dr = (cfg or {}).get("desiredRetention")
    new_per_day = ((cfg or {}).get("new") or {}).get("perDay")

    subtree = subtree_of(deck, names)
    # 坑6 防御：cardReviews 只接受 deckNames 里逐字存在的名字（subtree 即来自 deckNames）
    rev = []
    for d in subtree:
        rev += ac("cardReviews", deck=d, startID=start_ms) or []

    review_type = mature = mature_ok = review_ok = 0
    per_day = {}
    schema_warn = 0
    learn_cids = set()  # 窗口内出现过学习记录(type==0)的卡 → 实测新卡引入量
    for r in rev:
        if not isinstance(r, list) or len(r) < 9:  # shape-guard：结构漂移不崩、计数上报
            schema_warn += 1
            continue
        day = datetime.datetime.fromtimestamp(r[0] / 1000).strftime("%Y-%m-%d")
        per_day[day] = per_day.get(day, 0) + 1
        if r[8] == 0:
            learn_cids.add(r[1])
        ease, ivl, typ = r[3], r[4], r[8]
        if typ == 1:
            review_type += 1
            if ease >= 2:
                review_ok += 1
            if ivl > 21:
                mature += 1
                if ease >= 2:
                    mature_ok += 1
    ret_mature = round(mature_ok / mature, 4) if mature else None
    ret_all = round(review_ok / review_type, 4) if review_type else None

    gates = None
    if dr is not None and ret_mature is not None:
        gates = {"margin": ret_mature < dr - 0.05,
                 "sample": mature >= 200,
                 "duration": days >= 30,
                 "verdict": "偏低成立" if (ret_mature < dr - 0.05 and mature >= 200 and days >= 30)
                            else "不成立/观察中（未同时过三道闸）"}

    stats = ac("getDeckStats", decks=subtree)
    due_today = sum(s.get("review_count", 0) for s in (stats or {}).values())
    last7 = [per_day.get((datetime.date.today() - datetime.timedelta(days=i)).isoformat(), 0) for i in range(7)]
    avg7 = round(sum(last7) / 7, 1)
    backlog_days = round(due_today / avg7, 1) if avg7 > 0 else None

    streak = 0
    if per_day:
        cur = datetime.date.today()
        if cur.isoformat() not in per_day:
            cur -= datetime.timedelta(days=1)
        while cur.isoformat() in per_day:
            streak += 1
            cur -= datetime.timedelta(days=1)

    leech_ids = ac("findCards", query="%s prop:lapses>=8" % qdeck(deck)) or []
    leeches = []
    if leech_ids:
        cards = ac("cardsInfo", cards=leech_ids) or []
        note_ids = sorted({c.get("note") for c in cards if c.get("note")})
        for n in (ac("notesInfo", notes=note_ids) or [])[:10]:
            r = note_row(n, {})
            lap = max((c.get("lapses", 0) for c in cards if c.get("note") == n.get("noteId")), default=0)
            leeches.append({"noteId": n.get("noteId"), "lapses": lap, "front": r["front"]})

    # 预测（2026-08-16 修正）：基准必须是【实测新卡引入速率】，不是 config 的 perDay 上限。
    # 配置上限只是水龙头开度，没在跑就不算数；再加物理封顶：稳态复习/天不可能超过牌组总卡数。
    actual_new = round(len(learn_cids) / days, 2) if days else 0.0
    total_cards = len(ac("findCards", query=qdeck(deck)) or [])
    forecast = forecast_basis = None
    forecast_capped = False
    if dr:
        if actual_new > 0:
            forecast_basis = "actual"
            base = actual_new
        elif new_per_day:
            forecast_basis = "config-assumption"  # 没实测引入，只能算"假设按上限跑满"
            base = new_per_day
        else:
            base = None
        if base is not None:
            forecast = round(base * k_for_dr(dr))
            if total_cards and forecast > total_cards:
                forecast = total_cards
                forecast_capped = True

    try:
        fsrs = post(BRIDGE_URL, "fsrsStatus", {"deck": deck}, timeout=5)
    except Exception:
        fsrs = {"available": False,
                "fsrsEnabledGuess": (cfg or {}).get("fsrsParams6") is not None}
    intent_raw = read_intent()
    intent = (intent_raw or {}).get("decks", {}).get(deck) or (intent_raw or {}).get("global")

    out = {
        "schemaVersion": SCHEMA_VERSION,
        "deck": deck, "windowDays": days,
        "configFrom": cfg_deck, "desiredRetention": dr, "newPerDay": new_per_day,
        "subtreeDecks": subtree,
        "revlog": {"records": len(rev), "reviewType": review_type,
                   "retentionAll": ret_all, "mature": mature, "matureOk": mature_ok,
                   "retentionMature": ret_mature, "schemaWarnRows": schema_warn},
        "gates": gates,
        "load": {"dueReviewToday": due_today, "avgPerDayLast7": avg7,
                 "backlogDays": backlog_days, "streakDays": streak,
                 "activeDays": len(per_day),
                 "perDay": {k: per_day[k] for k in sorted(per_day)}},
        "forecast": {"perDay": forecast, "basis": forecast_basis,
                     "actualNewPerDay": actual_new, "configNewPerDay": new_per_day,
                     "kUsed": k_for_dr(dr) if dr else None,
                     "cappedByTotalCards": forecast_capped, "totalCards": total_cards},
        "leechCount": len(leech_ids), "leeches": leeches,
        "fsrs": fsrs, "intent": intent,
        "ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return EXIT_OK

    print("诊断采集：%s（含 %d 个子牌组）· 近 %d 天 · 配置来自 %s" % (deck, len(subtree) - 1, days, cfg_deck or "?"))
    print("目标 DR=%s ｜ 新卡/天=%s ｜ FSRS=%s%s" % (
        dr, new_per_day,
        fsrs.get("fsrsEnabled", fsrs.get("fsrsEnabledGuess", "?")),
        "" if fsrs.get("available") is not False else "（bridge 未装，由 config 推断）"))
    if ret_mature is None:
        print("保留率：样本不足（mature 复习 %d 次 < 200），不下判断；含新卡答对率 %s" % (mature, ret_all))
    else:
        verdict = gates["verdict"] if gates else "无 DR 基准（未读到牌组配置）"
        print("保留率：%s%% vs DR %s%%（mature 样本 %d）→ %s" % (
            round(ret_mature * 100, 1), round((dr or 0) * 100, 1), mature, verdict))
    print("负载：今日到期 %d ｜ 近7天日均 %s ｜ 欠账 %s 天 ｜ 连续 %d 天（%d 天有复习）" % (
        due_today, avg7, backlog_days, streak, len(per_day)))
    if forecast is None:
        print("预测：无法预测（无实测新卡引入，也未读到新卡上限设置）")
    elif forecast_basis == "actual":
        cap = "（已被牌组总卡数 %d 封顶）" % total_cards if forecast_capped else ""
        print("预测：稳态 ≈%s 复习/天（实测新卡 %s 张/天 × k=%s，经验系数）%s"
              % (forecast, actual_new, k_for_dr(dr), cap))
        if new_per_day and actual_new < new_per_day * 0.5:
            print("       ⚠ 设置的新卡上限 %s/天 没在跑满——若按上限加，复习量会更高" % new_per_day)
    else:  # config-assumption
        print("预测：不适用——近 %d 天实际引入新卡 %s 张/天，系数法没有输入。" % (days, actual_new))
        print("       假设按设置上限 %s/天 跑满，理论值 ≈%s 复习/天，但受牌组总量 %d 张封顶——现实最多每天几张。"
              % (new_per_day, round((new_per_day or 0) * k_for_dr(dr)), total_cards))
    print("leech：%d 张%s" % (len(leech_ids), "" if not leeches else "（" + "；".join(
        "#%s 忘%d次 %s" % (l["noteId"], l["lapses"], l["front"][:30]) for l in leeches[:3]) + "）"))
    if intent:
        print("意图：%s（配方 %s，设于 %s）" % (intent.get("goal"), intent.get("recipe"), str(intent.get("setAt", ""))[:10]))
    else:
        print("意图：未设（诊断将倾向 FSRS 通用最优，建议先问用户目标）")
    return EXIT_OK


# ---------------------------------------------------------------- selftest

def cmd_selftest(args):
    """对上游做形状探针：Anki 升级后跑一遍，即可发现返回结构漂移（AnkiConnect 无公开 schema）。"""
    names = ac("deckNames")
    results = []

    def probe(name, fn):
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, "%s: %s" % (type(e).__name__, str(e)[:100])
        results.append({"probe": name, "ok": bool(ok), "detail": str(detail)})

    probe("version==6", lambda: (ac("version") == 6, "AnkiConnect API v6"))
    probe("deckNames: list[str]",
          lambda: (isinstance(names, list) and all(isinstance(x, str) for x in names),
                   "%d 个牌组" % len(names)))

    def _find(shape_action, query):
        r = ac(shape_action, query=query)
        return isinstance(r, list) and all(isinstance(x, int) for x in r), "%d 条" % len(r or [])

    probe("findCards: list[int]", lambda: _find("findCards", "deck:%s" % ("*" if not names else '"%s"' % names[0])))
    probe("findNotes: list[int]", lambda: _find("findNotes", "deck:%s" % ("*" if not names else '"%s"' % names[0])))

    note_ids = ac("findNotes", query="*") or []
    if note_ids:
        def _notesinfo():
            r = ac("notesInfo", notes=note_ids[:3]) or []
            ok = all(isinstance(n.get("fields"), dict) for n in r)
            return ok, "%d 条，fields=dict" % len(r)
        probe("notesInfo: fields=dict", _notesinfo)
    else:
        results.append({"probe": "notesInfo: fields=dict", "ok": True, "detail": "SKIP：库里没有笔记"})

    deck = args.deck if args.deck and args.deck in names else (names[0] if names else None)
    if deck:
        start = int((time.time() - 7 * 86400) * 1000)
        def _cardreviews():
            rows = ac("cardReviews", deck=deck, startID=start) or []
            ok = all(isinstance(r, list) and len(r) >= 9 for r in rows)
            return ok, "%d 行 revlog，行长>=9：%s" % (len(rows), ok)
        probe("cardReviews: 行长>=9（deck=%s）" % deck, _cardreviews)

        def _config():
            cfg = ac("getDeckConfig", deck=deck)
            return isinstance(cfg, dict) and len(cfg) > 0, "keys=%d" % len(cfg or {})
        probe("getDeckConfig: dict", _config)

        def _stats():
            st = ac("getDeckStats", decks=[deck])
            v = list((st or {}).values())
            ok = bool(v) and all(isinstance(x.get("review_count"), int) for x in v)
            return ok, "review_count=int"
        probe("getDeckStats: review_count=int", _stats)
    else:
        results.append({"probe": "cardReviews/config/stats", "ok": True, "detail": "SKIP：无牌组"})

    def _byday():
        r = ac("getNumCardsReviewedByDay") or []
        ok = all(isinstance(x, list) and len(x) == 2 for x in r)
        return ok, "%d 天记录，[date,count] 对" % len(r)
    probe("getNumCardsReviewedByDay: [date,count]", _byday)

    failed = [r for r in results if not r["ok"]]
    if args.json:
        print(json.dumps({"schemaVersion": SCHEMA_VERSION, "failed": len(failed), "probes": results},
                         ensure_ascii=False, indent=1))
    else:
        for r in results:
            mark = "✓" if r["ok"] else "✗"
            print("%s %-42s %s" % (mark, r["probe"], r["detail"]))
        print("结论：%d 项探针，%d 项失败%s" % (len(results), len(failed),
                                      "——接口结构漂移，请降级 curl 手工流程并更新 anki-control.md 白名单" if failed else ""))
    return EXIT_ANKI if failed else EXIT_OK


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(prog="anki_probe.py", description="anki-tutor 只读探测（v1）")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON（默认人读摘要）")
    # 子命令级同名 --json：default=SUPPRESS 避免覆盖顶层已解析的值（--json 放子命令前后均可）
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="输出机器可读 JSON（默认人读摘要）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", parents=[common], help="连通性 + 牌组树")
    sub.add_parser("shells", parents=[common], help="空壳牌组扫描")
    p = sub.add_parser("dedup", parents=[common], help="查重候选拉取")
    p.add_argument("--deck", required=True)
    p.add_argument("--query", required=True, help="关键词/搜索语法（deck 限定由脚本加）")
    p = sub.add_parser("collect", parents=[common], help="诊断数据采集")
    p.add_argument("--deck", required=True)
    p.add_argument("--days", type=int, default=30)
    p = sub.add_parser("selftest", parents=[common], help="上游返回形状探针（schema 漂移检测）")
    p.add_argument("--deck")
    args = ap.parse_args()

    try:
        return {"check": cmd_check, "shells": cmd_shells, "dedup": cmd_dedup,
                "collect": cmd_collect, "selftest": cmd_selftest}[args.cmd](args)
    except AnkiDown as e:
        sys.stderr.write("[连接失败] %s —— 99%% 是 Anki 没开。请先打开 Anki 桌面端再试。(%s)\n" % (ANKI_URL, e))
        return EXIT_CONN
    except RuntimeError as e:
        sys.stderr.write("[Anki 返回错误] %s\n" % e)
        return EXIT_ANKI


if __name__ == "__main__":
    sys.exit(main())
