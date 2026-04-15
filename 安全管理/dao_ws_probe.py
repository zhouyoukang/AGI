"""
dao_ws_probe.py — 道法自然 · 双机 Windsurf 对话备份探针
================================================================
探测本机 + 笔记本(192.168.31.179) 的 Windsurf 对话备份状态,
供 security_hub.py 的 /api/ws_probe 和 Dashboard 使用.

功能:
  get_local_backup_status()   — 本机 backup/stats.json
  get_remote_backup_status()  — 笔记本 SMB/UNC backup/stats.json
  get_monitor_status()        — 本机 windsurf_hot_monitor :19900
  get_remote_monitor_status() — 笔记本 windsurf_hot_monitor :19900
  trigger_local_backup()      — 后台触发 dao_backup.py
  trigger_remote_backup()     — WinRM 触发笔记本备份
  get_unified_status()        — 统一双机摘要
  get_cached_unified()        — 带缓存版本 (60s TTL)
"""
import sys, os, json, time, socket, http.client, subprocess, threading
from pathlib import Path
from datetime import datetime

ROOT       = Path(__file__).parent.parent
LOCAL_WS   = ROOT
BACKUP_DIR = ROOT / "Windsurf万法归宗" / "对话追踪" / "backup"
BACKUP_PY  = ROOT / "Windsurf万法归宗" / "对话追踪" / "dao_backup.py"

_LAPTOP_ROOTS = [
    Path(r"N:\道\道生一\一生二"),
    Path(r"M:\道\道生一\一生二"),
    Path(r"\\192.168.31.179\道\道生一\一生二"),
]
LAPTOP_IP        = "192.168.31.179"
_laptop_ws_cache = {"path": None, "ts": 0}

_cache = {}
_CACHE_TTL = 60


def _cached(key, fn, default=None):
    now = time.time()
    if key in _cache and now - _cache[key]["ts"] < _CACHE_TTL:
        return _cache[key]["data"]
    try:
        data = fn()
        _cache[key] = {"data": data, "ts": now}
        return data
    except Exception as e:
        return default or {"error": str(e)}


def _find_laptop_ws():
    now = time.time()
    if _laptop_ws_cache["path"] and now - _laptop_ws_cache["ts"] < 300:
        return _laptop_ws_cache["path"]
    for candidate in _LAPTOP_ROOTS:
        try:
            p = Path(str(candidate))
            if p.exists() and (p / "Windsurf万法归宗").exists():
                _laptop_ws_cache["path"] = p
                _laptop_ws_cache["ts"] = now
                return p
        except Exception:
            continue
    return None


def _probe_http(host, port, path, timeout=3):
    try:
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
        conn.request("GET", path)
        resp = conn.getresponse()
        if resp.status == 200:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        pass
    return None


def _check_port(host, port, timeout=1):
    try:
        s = socket.socket()
        s.settimeout(timeout)
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False


def _ago_str(ts: int) -> str:
    if not ts:
        return "never"
    diff = int(time.time()) - ts
    if diff < 60:    return f"{diff}s ago"
    elif diff < 3600: return f"{diff//60}m ago"
    elif diff < 86400: return f"{diff//3600}h ago"
    return f"{diff//86400}d ago"


def get_local_backup_status() -> dict:
    result = {"machine": "desktop", "available": False, "backup_dir": str(BACKUP_DIR),
              "total_conversations": 0, "total_steps": 0, "tokens_in": 0, "tokens_out": 0}
    stats_path = BACKUP_DIR / "stats.json"
    index_path = BACKUP_DIR / "index.json"
    if not stats_path.exists():
        return result
    try:
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
        result.update({"available": True, "total_conversations": stats.get("total", 0),
                       "total_steps": stats.get("total_steps", 0),
                       "tokens_in": stats.get("tokens_in", 0),
                       "tokens_out": stats.get("tokens_out", 0),
                       "models": stats.get("models", {}), "monthly": stats.get("monthly", {}),
                       "generated_at": stats.get("generated_at", "")})
        if stats.get("generated_at"):
            result["ago"] = _ago_str(int(datetime.strptime(stats["generated_at"], "%Y-%m-%d %H:%M:%S").timestamp()))
        if index_path.exists():
            idx = json.loads(index_path.read_text(encoding="utf-8"))
            convs = idx.get("conversations", [])
            if convs:
                result["latest_conv"] = convs[0].get("title", "")[:60]
    except Exception as e:
        result["error"] = str(e)
    return result


def get_remote_backup_status() -> dict:
    result = {"machine": "laptop", "available": False, "laptop_ip": LAPTOP_IP,
              "smb_available": False, "winrm_available": False,
              "total_conversations": 0, "total_steps": 0}
    result["winrm_available"] = _check_port(LAPTOP_IP, 5985, timeout=1)
    result["ping_ok"] = _check_port(LAPTOP_IP, 445, timeout=1)
    laptop_ws = _find_laptop_ws()
    if not laptop_ws:
        result["error"] = "SMB路径不可达"
        return result
    result["smb_available"] = True
    result["smb_path"] = str(laptop_ws)
    stats_path = laptop_ws / "Windsurf万法归宗" / "对话追踪" / "backup" / "stats.json"
    if not stats_path.exists():
        result["error"] = "笔记本尚未运行 dao_backup.py"
        return result
    try:
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
        result.update({"available": True, "total_conversations": stats.get("total", 0),
                       "total_steps": stats.get("total_steps", 0),
                       "generated_at": stats.get("generated_at", "")})
    except Exception as e:
        result["error"] = str(e)
    return result


def get_monitor_status(host="127.0.0.1", port=19900) -> dict:
    base = {"host": host, "port": port, "online": False}
    health = _probe_http(host, port, "/api/health", timeout=2)
    if not health:
        base["error"] = "monitor offline"
        return base
    base.update({"online": True, "uptime_sec": health.get("uptime_sec", 0),
                 "conv_count": health.get("conv_count", 0)})
    return base


def get_remote_monitor_status() -> dict:
    base = {"host": LAPTOP_IP, "port": 19900, "online": False}
    if not _check_port(LAPTOP_IP, 19900, timeout=1):
        base["error"] = "笔记本 monitor 未运行"
        return base
    health = _probe_http(LAPTOP_IP, 19900, "/api/health", timeout=3)
    if health:
        base.update({"online": True, "uptime_sec": health.get("uptime_sec", 0),
                     "conv_count": health.get("conv_count", 0)})
    return base


_trigger_lock = threading.Lock()
_last_trigger = {"local": 0, "remote": 0}
_TRIGGER_COOLDOWN = 60

def trigger_local_backup(force=False) -> dict:
    if not BACKUP_PY.exists():
        return {"ok": False, "error": f"dao_backup.py not found"}
    with _trigger_lock:
        if time.time() - _last_trigger["local"] < _TRIGGER_COOLDOWN and not force:
            return {"ok": False, "reason": "cooldown"}
        _last_trigger["local"] = time.time()
    def _run():
        try:
            cmd = [sys.executable, str(BACKUP_PY)] + (["--full"] if force else [])
            subprocess.run(cmd, capture_output=True, timeout=300,
                           creationflags=0x08000000 if sys.platform == "win32" else 0)
            _cache.pop("local_backup", None)
            _cache.pop("unified", None)
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True, "status": "triggered"}


def trigger_remote_backup(force=False) -> dict:
    if not _check_port(LAPTOP_IP, 5985, timeout=2):
        laptop_ws = _find_laptop_ws()
        if laptop_ws:
            trigger_file = laptop_ws / "Windsurf万法归宗" / "对话追踪" / ".backup_trigger"
            try:
                trigger_file.write_text(f'{{"ts":{int(time.time())},"force":{str(force).lower()}}}')
                return {"ok": True, "method": "smb_trigger_file"}
            except Exception as e:
                return {"ok": False, "error": str(e)}
        return {"ok": False, "error": "WinRM不可达"}
    laptop_ws = _find_laptop_ws()
    if not laptop_ws:
        return {"ok": False, "error": "无法确定笔记本工作区路径"}
    args_flag = "--full" if force else ""
    ps_cmd = (f'Invoke-Command -ComputerName {LAPTOP_IP} -ScriptBlock {{'
              f' cd "E:\\道\\道生一\\一生二\\Windsurf万法归宗\\对话追踪";'
              f' python dao_backup.py {args_flag}}}' )
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd],
                           capture_output=True, text=True, timeout=120,
                           creationflags=0x08000000 if sys.platform == "win32" else 0)
        if r.returncode == 0:
            return {"ok": True, "method": "winrm"}
        return {"ok": False, "method": "winrm", "error": r.stderr[-200:]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_unified_status() -> dict:
    local   = get_local_backup_status()
    remote  = get_remote_backup_status()
    mon_loc = get_monitor_status()
    mon_rem = get_remote_monitor_status()
    return {
        "ts": int(time.time()),
        "dt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "desktop": {"backup": local,  "monitor": mon_loc},
        "laptop":  {"backup": remote, "monitor": mon_rem},
        "combined": {
            "total_conversations": local.get("total_conversations", 0) + remote.get("total_conversations", 0),
            "total_steps":  local.get("total_steps", 0) + remote.get("total_steps", 0),
        },
        "health": {
            "local_backup_ok":   local.get("available", False),
            "remote_backup_ok":  remote.get("available", False),
            "local_monitor_ok":  mon_loc.get("online", False),
            "remote_monitor_ok": mon_rem.get("online", False),
            "laptop_reachable":  remote.get("smb_available", False) or remote.get("winrm_available", False),
        }
    }


def get_cached_unified() -> dict:
    return _cached("unified", get_unified_status,
                   {"error": "probe failed", "ts": 0, "desktop": {}, "laptop": {}, "combined": {}, "health": {}})


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    import argparse as _ap
    p = _ap.ArgumentParser(description="道法自然 · 双机 Windsurf 对话备份探针")
    p.add_argument("--trigger", choices=["local", "remote", "both"])
    p.add_argument("--force", action="store_true")
    args = p.parse_args()
    if args.trigger:
        if args.trigger in ("local", "both"):
            print(json.dumps(trigger_local_backup(force=args.force), ensure_ascii=False, indent=2))
        if args.trigger in ("remote", "both"):
            print(json.dumps(trigger_remote_backup(force=args.force), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(get_unified_status(), ensure_ascii=False, indent=2, default=str))
