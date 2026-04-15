#!/usr/bin/env python3
"""
道法自然 · dao_daemon.py
无为而无不为 — 主持久化守护进程
管理所有子服务: security_hub / windsurf_monitor / terminal_watchdog / dao_autosave
执行定时任务: dao_backup (每2小时)
"""
import sys, os, json, time, subprocess, socket, signal, logging
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE    = Path(__file__).parent.resolve()
ROOT    = HERE.parent
TRACKER = ROOT / 'Windsurf万法归宗' / '对话追踪'
PYTHON  = sys.executable

SERVICES = [
    {
        "name":         "security_hub",
        "script":       str(HERE / "security_hub.py"),
        "cwd":          str(HERE),
        "health_port":  9877,
        "init_delay":   3,
        "restart_base": 5,
        "restart_max":  120,
    },
    {
        "name":         "windsurf_monitor",
        "script":       str(TRACKER / "windsurf_hot_monitor.py"),
        "cwd":          str(TRACKER),
        "health_port":  19900,
        "init_delay":   8,
        "restart_base": 5,
        "restart_max":  120,
    },
    {
        "name":         "terminal_watchdog",
        "script":       str(HERE / "terminal_watchdog_v2.py"),
        "args":         ["--daemon"],
        "cwd":          str(HERE),
        "health_port":  None,
        "init_delay":   2,
        "restart_base": 5,
        "restart_max":  60,
    },
    {
        "name":         "dao_autosave",
        "script":       str(TRACKER / "dao_autosave.py"),
        "cwd":          str(TRACKER),
        "health_port":  19901,
        "init_delay":   12,
        "restart_base": 10,
        "restart_max":  120,
    },
    {
        "name":         "ws_wal_guardian",
        "script":       str(HERE / "ws_wal_guardian.py"),
        "cwd":          str(HERE),
        "health_port":  9879,
        "init_delay":   6,
        "restart_base": 10,
        "restart_max":  120,
    },
    {
        "name":         "ls_watchdog",
        "script":       str(HERE / "ls_watchdog.py"),
        "cwd":          str(HERE),
        "health_port":  None,
        "init_delay":   15,
        "restart_base": 30,
        "restart_max":  300,
    },
]

PERIODIC = [
    {
        "name":         "dao_backup",
        "script":       str(TRACKER / "dao_backup.py"),
        "cwd":          str(TRACKER),
        "interval_s":   7200,
        "run_on_start": True,
    },
]

STATE_FILE = HERE / "_daemon_state.json"
LOG_FILE   = HERE / "_daemon.log"
PID_FILE   = HERE / "_daemon.pid"

_handler = RotatingFileHandler(
    LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
)
_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)-5s] %(message)s'))
_root_log = logging.getLogger()
_root_log.setLevel(logging.INFO)
_root_log.addHandler(_handler)
log = logging.getLogger("daemon")

_procs         : dict = {}
_restart_delay : dict = {}
_restart_at    : dict = {}
_periodic_last : dict = {}
_stop          : bool = False


def _is_alive(name: str) -> bool:
    proc = _procs.get(name)
    if proc is not None and proc.poll() is None:
        return True
    svc = next((s for s in SERVICES if s["name"] == name), None)
    if svc and svc.get("health_port") and _port_listening(svc["health_port"]):
        return True
    return False


def _port_listening(port, timeout: float = 0.5) -> bool:
    if port is None:
        return False
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def _spawn(script: str, cwd: str, args: list = None) -> subprocess.Popen:
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8:replace'
    env['PYTHONUTF8'] = '1'
    cmd = [PYTHON, script] + (args or [])
    return subprocess.Popen(
        cmd, cwd=cwd,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=flags, env=env,
    )


def _start_service(svc: dict):
    name   = svc["name"]
    script = svc["script"]
    if not Path(script).exists():
        log.error(f"[{name}] script missing: {script}")
        return
    port = svc.get("health_port")
    if port and _port_listening(port):
        log.info(f"[{name}] port {port} already listening, skipping start")
        return
    try:
        proc = _spawn(script, svc["cwd"], svc.get("args"))
        _procs[name] = proc
        _restart_delay[name] = svc["restart_base"]
        log.info(f"[{name}] started PID={proc.pid}")
    except Exception as exc:
        log.error(f"[{name}] start failed: {exc}")


def _run_periodic(task: dict):
    name = task["name"]
    if not Path(task["script"]).exists():
        log.warning(f"[{name}] script missing")
        return
    try:
        _spawn(task["script"], task["cwd"])
        _periodic_last[name] = time.time()
        log.info(f"[{name}] periodic task launched")
    except Exception as exc:
        log.error(f"[{name}] periodic launch failed: {exc}")


def _save_state():
    now = time.time()
    state = {
        "ts":  int(now),
        "dt":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "pid": os.getpid(),
        "services": {
            svc["name"]: {
                "alive":    _is_alive(svc["name"]),
                "pid":      _procs[svc["name"]].pid if _procs.get(svc["name"]) else None,
                "port":     svc.get("health_port"),
                "port_ok":  _port_listening(svc.get("health_port")),
            }
            for svc in SERVICES
        },
        "periodic": {
            t["name"]: {
                "last_run":   _periodic_last.get(t["name"]),
                "next_run":   (_periodic_last.get(t["name"]) or 0) + t["interval_s"],
                "interval_s": t["interval_s"],
            }
            for t in PERIODIC
        },
    }
    try:
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    except Exception:
        pass


def _on_signal(sig, frame):
    global _stop
    log.info(f"Signal {sig} received, shutting down...")
    _stop = True
    for name, proc in _procs.items():
        try:
            proc.terminate()
        except Exception:
            pass


def main():
    global _stop
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            import psutil
            if psutil.pid_exists(old_pid):
                proc = psutil.Process(old_pid)
                if 'dao_daemon' in ' '.join(proc.cmdline()):
                    log.warning(f"dao_daemon already running (PID={old_pid}), exiting")
                    return
        except Exception:
            pass
    PID_FILE.write_text(str(os.getpid()))

    log.info("=" * 60)
    log.info(f"dao_daemon v1.0 started  PID={os.getpid()}")
    log.info(f"Managing {len(SERVICES)} services, {len(PERIODIC)} periodic tasks")
    log.info("=" * 60)

    signal.signal(signal.SIGTERM, _on_signal)
    try:
        signal.signal(signal.SIGINT, _on_signal)
    except Exception:
        pass

    for i, svc in enumerate(SERVICES):
        if i > 0:
            time.sleep(2)
        _start_service(svc)

    warmup_done  = False
    warmup_after = time.time() + 15
    last_state_ts = 0

    while not _stop:
        now = time.time()
        if not warmup_done and now >= warmup_after:
            warmup_done = True
            for task in PERIODIC:
                if task.get("run_on_start"):
                    _run_periodic(task)

        for svc in SERVICES:
            name = svc["name"]
            if _is_alive(name):
                _restart_delay[name] = svc["restart_base"]
                continue
            next_restart = _restart_at.get(name, 0)
            if now < next_restart:
                continue
            delay = _restart_delay.get(name, svc["restart_base"])
            log.warning(f"[{name}] exited, restart in {delay}s")
            _start_service(svc)
            _restart_at[name]    = now + delay
            _restart_delay[name] = min(delay * 2, svc["restart_max"])

        if warmup_done:
            for task in PERIODIC:
                last = _periodic_last.get(task["name"]) or 0
                if now - last >= task["interval_s"]:
                    _run_periodic(task)

        if now - last_state_ts >= 30:
            _save_state()
            last_state_ts = now

        time.sleep(15)

    _save_state()
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass
    log.info("dao_daemon stopped cleanly")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="道法自然 · 主持久化守护进程")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--stop",   action="store_true")
    args = parser.parse_args()
    if args.status:
        if STATE_FILE.exists():
            print(json.dumps(json.loads(STATE_FILE.read_text(encoding='utf-8')), ensure_ascii=False, indent=2))
        else:
            print("[!] 守护进程未运行")
        sys.exit(0)
    if args.stop:
        if PID_FILE.exists():
            pid = int(PID_FILE.read_text().strip())
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"[OK] 已发送 SIGTERM 到 PID={pid}")
            except ProcessLookupError:
                print(f"[!] PID={pid} 不存在")
        sys.exit(0)
    main()
