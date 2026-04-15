"""
dao_autosave_probe.py — 道之永存 · 自动保存探针
================================================
轻量探针, 供 security_hub.py 导入, 读取道之永存守护状态.

提供:
  get_autosave_status()    — 读取永存/stats.json + index.json 摘要
  get_autosave_health()    — 健康评分 (守护是否在线 + 数据新鲜度 + 对话数)
  trigger_autosave()       — 通过 HTTP API 触发立即保存
  get_cached_autosave()    — 带缓存的统一状态 (供 security_hub 快速调用)
"""

import json
import http.client
import socket
import time
from datetime import datetime
from pathlib import Path

ROOT       = Path(__file__).parent.parent
TRACKER    = ROOT / "Windsurf万法归宗" / "对话追踪"
SAVE_ROOT  = TRACKER / "永存"
INDEX_FILE = SAVE_ROOT / "index.json"
STATS_FILE = SAVE_ROOT / "stats.json"
STATE_FILE = SAVE_ROOT / ".daemon_state.json"
PID_FILE   = SAVE_ROOT / ".daemon.pid"

API_PORT   = 19901
_CACHE     = {}
_CACHE_TTL = 30


def _cached(key, fn, default=None):
    now = time.time()
    if key in _CACHE and now - _CACHE[key]["ts"] < _CACHE_TTL:
        return _CACHE[key]["data"]
    try:
        data = fn()
        _CACHE[key] = {"data": data, "ts": now}
        return data
    except Exception as e:
        return default or {"error": str(e)}


def _port_listening(port=API_PORT, timeout=1.0):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def _api_get(path, timeout=3):
    try:
        conn = http.client.HTTPConnection("127.0.0.1", API_PORT, timeout=timeout)
        conn.request("GET", path)
        resp = conn.getresponse()
        data = json.loads(resp.read())
        conn.close()
        return data
    except Exception:
        return None


def _read_json(p):
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def get_autosave_status():
    result = {"available": False, "daemon_online": False,
              "save_root": str(SAVE_ROOT), "save_root_exists": SAVE_ROOT.exists()}
    result["daemon_online"] = _port_listening()
    if result["daemon_online"]:
        api_status = _api_get("/api/status")
        if api_status:
            result["available"] = True
            result["api"] = api_status
    stats = _read_json(STATS_FILE)
    if stats:
        result["available"] = True
        result["stats"] = stats
    index_data = _read_json(INDEX_FILE)
    if index_data:
        convs = index_data.get("conversations", []) if isinstance(index_data, dict) else index_data
        result["conversation_count"] = len(convs)
        sorted_convs = sorted(convs, key=lambda x: x.get("ts_update", 0), reverse=True)
        result["recent"] = [
            {"id": c.get("id", "")[:8], "title": (c.get("title") or "untitled")[:50],
             "steps": c.get("step_count", 0), "updated": c.get("save_dt", "")}
            for c in sorted_convs[:5]
        ]
    state = _read_json(STATE_FILE)
    if state:
        result["daemon_state"] = {
            "pid": state.get("pid"), "cycle": state.get("cycle", 0),
            "last_save": state.get("last_save_dt"), "uptime": state.get("uptime"),
            "conversations_saved": state.get("conversations_saved", 0),
        }
    if PID_FILE.exists():
        try:
            result["daemon_pid"] = int(PID_FILE.read_text().strip())
        except Exception:
            pass
    return result


def get_autosave_health():
    score = 0
    issues = []
    status = get_autosave_status()
    if status.get("daemon_online"):
        score += 40
    else:
        issues.append("守护进程离线")
    conv_count = status.get("conversation_count", 0)
    if conv_count > 0:
        score += 20
    else:
        issues.append("无保存数据")
    daemon_state = status.get("daemon_state", {})
    last_save = daemon_state.get("last_save")
    if last_save:
        try:
            last_dt = datetime.strptime(last_save, "%Y-%m-%d %H:%M:%S")
            age_minutes = (datetime.now() - last_dt).total_seconds() / 60
            if age_minutes < 60:
                score += 20
            elif age_minutes < 360:
                score += 10
            else:
                issues.append(f"数据陈旧({int(age_minutes)}分钟前)")
        except Exception:
            pass
    stats = status.get("stats", {})
    total_steps = stats.get("total_steps", 0)
    if total_steps > 100:
        score += 20
    elif total_steps > 0:
        score += 10
    grade = "S" if score >= 90 else "A" if score >= 70 else "B" if score >= 50 else "C"
    return {
        "score": min(score, 100), "grade": grade,
        "daemon_online": status.get("daemon_online", False),
        "conversations": conv_count, "total_steps": total_steps,
        "issues": issues, "last_save": daemon_state.get("last_save"),
    }


def trigger_autosave():
    if not _port_listening():
        return {"ok": False, "error": "守护进程离线"}
    result = _api_get("/api/trigger")
    return result or {"ok": False, "error": "API 无响应"}


def get_autosave_dashboard():
    status = get_autosave_status()
    health = get_autosave_health()
    return {
        "health": health, "daemon_online": status.get("daemon_online", False),
        "daemon_pid": status.get("daemon_pid"),
        "conversations": status.get("conversation_count", 0),
        "stats": status.get("stats", {}), "recent": status.get("recent", []),
        "save_root": str(SAVE_ROOT),
    }


def get_cached_autosave():
    return _cached("unified", get_autosave_dashboard, {
        "health": {"score": 0, "grade": "?"}, "daemon_online": False, "conversations": 0,
    })
