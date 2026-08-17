# fsrs_bridge 的三个 action 实现。全部跑在 Qt 主线程（web.py 的 QTimer 回调），
# 可直接访问 mw.col。
#
# 版本依赖：FSRS 全套（compute_fsrs_params + update_deck_configs +
# COMPUTE_ALL_PARAMS）需要 Anki >= 24.0。低于此版本直接报错。
#
# API 契约（与 AnkiConnect 一致，方便 CLI 复用调用方式）：
#   请求: {"action": "fsrsStatus"|"fsrsOptimize"|"fsrsApply", "version": 6, "params": {...}}
#   响应: {"result": {...}, "error": null}  或  {"result": null, "error": "..."}
#
# 关键 import 来源（一手源码核实）：
#   - ComputeFsrsParamsRequest: from anki.scheduler_pb2（不是 anki.collection！）
#   - UpdateDeckConfigsRequest / DeckConfig / UpdateDeckConfigsMode: from anki.deck_config_pb2

import aqt
from aqt import mw

MIN_VERSION = (24, 0)


def _anki_version_tuple():
    return tuple(int(x) for x in aqt.appVersion.split("."))


def _require_min_version():
    if _anki_version_tuple() < MIN_VERSION:
        raise RuntimeError(
            f"fsrs_bridge 需要 Anki >= {'.'.join(map(str, MIN_VERSION))}，"
            f"当前 {aqt.appVersion}"
        )


def _deck_id(name):
    # by_name 只查不建：decks.id() 是 get-or-create，会让"读"操作凭空建牌组
    # （实测：对不存在的牌组调 fsrsStatus 会在用户库里创建同名空牌组）
    deck = mw.col.decks.by_name(name)
    if not deck:
        raise RuntimeError(f"找不到牌组：{name}")
    return deck["id"]


def fsrs_status(req):
    """读 FSRS 状态：调度器类型、是否启用 FSRS、Anki 版本、距上次优化天数。

    params:
      {}                       —— 只返回全局调度器状态
      {"deck": "牌组名"}        —— 额外返回该牌组的 FSRS 开关 + 距上次优化天数
    """
    _require_min_version()
    info = {
        "ankiVersion": aqt.appVersion,
        "v3scheduler": bool(mw.col.v3_scheduler()),  # True = FSRS 可用（v3 调度器）
    }
    deck_name = req.get("deck")
    if deck_name:
        did = _deck_id(deck_name)
        cfg = mw.col.decks.get_deck_configs_for_update(did)
        info.update({
            "deck": deck_name,
            "fsrsEnabled": bool(cfg.fsrs),
            "daysSinceLastOptimize": int(cfg.days_since_last_fsrs_optimize),
        })
    return info


def fsrs_optimize(req):
    """优化 FSRS 权重（只算不写库、不 reschedule）。等价于 GUI 的 Optimize 按钮。

    两种传参方式：
      {"deck": "牌组名"}
        —— 自动构造 search='deck:"牌组名"'，并读取该牌组当前权重作 currentParams
      {"search": "deck:X", "currentParams": [...], "ignoreBeforeMs": 0,
       "numRelearningSteps": N, "healthCheck": true}
        —— 完全自定义

    返回: {"params": [权重数组，维度随 FSRS 版本（实测 Anki 26.05 = 21 维；
                      FSRS-5=17、FSRS-6=19，本函数 list() 自适应）],
           "fsrsItems": 参与训练的复习数,
           "healthCheckPassed": true|false|null（null=未做健康检查或数据不足）}
    """
    _require_min_version()
    from anki.scheduler_pb2 import ComputeFsrsParamsRequest

    if "search" in req:
        search = req["search"]
        current_params = req.get("currentParams", []) or []
    else:
        deck_name = req["deck"]
        did = _deck_id(deck_name)
        search = f'deck:"{deck_name}"'
        # 读当前权重作为 currentParams，让后端能判断"是否已最优"
        d = mw.col.decks.config_dict_for_deck_id(did)
        current_params = d.get("fsrsParams6") or d.get("fsrsParams5") or []

    request = ComputeFsrsParamsRequest(
        search=search,
        current_params=current_params,
        ignore_revlogs_before_ms=int(req.get("ignoreBeforeMs", 0)),
        num_of_relearning_steps=int(req.get("numRelearningSteps", 0)),
        health_check=bool(req.get("healthCheck", False)),
    )
    # _backend 的生成方法走 _raw 模式：传序列化字节，返回字节，再 FromString 解析
    # （参见 pylib/anki/decks.py:297 的 update_deck_configs_raw 范例）
    from anki.scheduler_pb2 import ComputeFsrsParamsResponse
    resp_bytes = mw.col._backend.compute_fsrs_params_raw(request.SerializeToString())
    resp = ComputeFsrsParamsResponse.FromString(resp_bytes)

    # health_check_passed 是 optional 字段：用 HasField 区分"未设"和"False"
    hcp = resp.health_check_passed if resp.HasField("health_check_passed") else None

    return {
        "params": list(resp.params),
        "fsrsItems": int(resp.fsrs_items),
        "healthCheckPassed": hcp,
    }


def fsrs_apply(req):
    """一步完成：优化全部 preset 参数 + 可选 reschedule（重排卡片到期日）。
    等价于 GUI 的 "Save & Optimize" + 确认 reschedule。

    params:
      {"deck": "牌组名", "fsrsReschedule": true（默认 true）, "healthCheck": false}

    ⚠ 执行期间 GUI 会冻结（几十秒），这是 QTimer 主线程模型的已知取舍。

    ⚠ 会改写卡片调度。skill 调用前应已让用户确认（同 SKILL.md 红线 1 精神）。
    """
    _require_min_version()
    from anki.deck_config_pb2 import UpdateDeckConfigsRequest, UpdateDeckConfigsMode

    deck_name = req["deck"]
    did = _deck_id(deck_name)
    fsrs_reschedule = bool(req.get("fsrsReschedule", True))
    health_check = bool(req.get("healthCheck", False))

    # 取该 deck 涉及的全部 config。直接用后端返回的完整 config 结构（c.config），
    # 避免手动重建 DeckConfig 丢失字段。COMPUTE_ALL_PARAMS 模式下后端会对每个
    # preset 重算 fsrs 参数。
    info = mw.col.decks.get_deck_configs_for_update(did)
    configs = [c.config for c in info.all_config]

    request = UpdateDeckConfigsRequest(
        target_deck_id=did,
        mode=UpdateDeckConfigsMode.UPDATE_DECK_CONFIGS_MODE_COMPUTE_ALL_PARAMS,
        fsrs=True,
        fsrs_reschedule=fsrs_reschedule,
        fsrs_health_check=health_check,
    )
    request.configs.extend(configs)  # repeated 字段用 extend 稳妥

    mw.col.decks.update_deck_configs(request)

    return {
        "applied": True,
        "deck": deck_name,
        "fsrsReschedule": fsrs_reschedule,
        "configCount": len(configs),
    }


def fsrs_set_enabled(req):
    """开启或关闭 FSRS 总开关（等价于 GUI 勾选/取消 FSRS）。

    params:
      {"deck": "牌组名", "enabled": true|false, "fsrsReschedule": true（默认 true）}

    开启：翻总开关 + 用 FSRS 重算全库记忆状态 + 可选重排卡片。
    关闭：翻总开关 + 清空所有卡的记忆状态（重新开可重算，但有损耗）。

    ⚠ 影响全库的长操作（GUI 也一样）。skill 调用前必须用户确认。
    ⚠ 翻 FSRS 开关唯一 GUI 等价方式是 update_deck_configs(fsrs=...)——
      Config.Bool 枚举里没有 Fsrs，不能单独 set_config_bool。
    """
    _require_min_version()
    from anki.deck_config_pb2 import UpdateDeckConfigsRequest, UpdateDeckConfigsMode

    deck_name = req["deck"]
    did = _deck_id(deck_name)
    enabled = bool(req["enabled"])
    fsrs_reschedule = bool(req.get("fsrsReschedule", True))

    info = mw.col.decks.get_deck_configs_for_update(did)
    configs = [c.config for c in info.all_config]

    # NORMAL 模式（只翻开关 + 重算记忆状态，不重新优化参数）。
    # fsrs 字段翻总开关；fsrs_toggled 后后端自动重算/清空 memory state。
    request = UpdateDeckConfigsRequest(
        target_deck_id=did,
        mode=UpdateDeckConfigsMode.UPDATE_DECK_CONFIGS_MODE_NORMAL,
        fsrs=enabled,
        fsrs_reschedule=fsrs_reschedule,
    )
    request.configs.extend(configs)

    mw.col.decks.update_deck_configs(request)
    return {
        "applied": True,
        "deck": deck_name,
        "fsrsEnabled": enabled,
        "fsrsReschedule": fsrs_reschedule,
    }


def fsrs_debug(req):
    """调试：探测 _backend/decks 的 FSRS 方法签名 + proto 字段，校准 API 调用。
    正常使用不需要调它；只在内部 API 名/签名不确定时用来拿 ground truth。"""
    import inspect
    import importlib

    def _sigs(obj, filt):
        out = {}
        for n in sorted(m for m in dir(obj) if filt(m) and not m.startswith("_")):
            attr = getattr(obj, n, None)
            if callable(attr):
                try:
                    out[n] = str(inspect.signature(attr))
                except (ValueError, TypeError):
                    out[n] = "(?)"
            else:
                out[n] = f"<{type(attr).__name__}>"
        return out

    proto_fields = {}
    for mod, cls in [("anki.scheduler_pb2", "ComputeFsrsParamsRequest"),
                     ("anki.scheduler_pb2", "ComputeFsrsParamsResponse"),
                     ("anki.deck_config_pb2", "UpdateDeckConfigsRequest")]:
        try:
            m = importlib.import_module(mod)
            C = getattr(m, cls)
            proto_fields[cls] = [f.name for f in C.DESCRIPTOR.fields]
        except Exception as e:
            proto_fields[cls] = f"err: {e}"

    return {
        "backendType": type(mw.col._backend).__name__,
        "backendMethods": _sigs(mw.col._backend,
                                lambda m: "fsrs" in m.lower() or "compute" in m.lower()),
        "decksMethods": _sigs(mw.col.decks,
                              lambda m: "deck_config" in m.lower()),
        "protoFields": proto_fields,
    }


DISPATCH = {
    "fsrsStatus": fsrs_status,
    "fsrsOptimize": fsrs_optimize,
    "fsrsApply": fsrs_apply,
    "fsrsSetEnabled": fsrs_set_enabled,
    "fsrsDebug": fsrs_debug,
}


def dispatch(req):
    """web.py 调这个入口。req 是解析后的 JSON dict。"""
    action = req.get("action")
    if action not in DISPATCH:
        raise RuntimeError(f"unsupported action: {action!r}（支持: {list(DISPATCH)}）")
    params = req.get("params", {}) or {}
    return DISPATCH[action](params)
