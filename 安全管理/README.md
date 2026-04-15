# 安全管理统一中枢

> 反者道之动，弱者道之用。一个Hub、一个端口、一个Dashboard。

## 架构

```
安全管理/
├── dao_daemon.py          ★ 主守护进程 (管理6子服务+定时任务, 开机自启)
├── security_hub.py        ★ 统一中枢 :9877 (40+ API, 10-Tab Dashboard)
├── windsurf_wisdom.py     ★ 智慧部署器 :9876 (规则+技能+工作流 泛化模板)
├── windsurf_monitor.py    ★ Windsurf监控引擎 (MCP/LS/扩展全景)
├── backup_engine.py       ★ 七层备份引擎 (SHA256指纹+WinRM+夸克云端)
├── dao_ws_probe.py        ★ 双机对话备份探针 (本机↔179状态/触发)
├── dao_autosave_probe.py  ★ 对话自动保存探针 (daemon状态检测)
├── disk_monitor.py          磁盘监控 (空间预警+大文件扫描)
├── security_tray.py         系统托盘监控器 (7种通知)
├── ls_watchdog.py           LS内存看门狗 (防OOM→对话中断)
├── ws_wal_guardian.py       WAL数据库守护
├── terminal_watchdog_v2.py  终端看门狗v2
├── git_safety_guard.py    ★ Git安全守护
├── →注册持久化.ps1          一键注册全部计划任务
├── →双机同步.ps1          ★ 双机Windsurf备份脚本同步 (WinRM推送到179)
├── →安全中枢.cmd             一键启动Hub
├── 密码管理/                  凭据子系统
└── _archive/                 已归档legacy文件

secrets.env   (项目根)  ← 唯一真相源 (gitignored)
凭据中心.md   (项目根)  ← 结构索引 (git tracked)
```

## 双机 Windsurf 对话底层资源备份

> 道法自然 · 无为而无不为 — 两台机器独立守护，GitHub为纽带

### 本机 (主力机)

| 组件 | 路径 | 作用 |
|------|------|------|
| `dao_autosave.py` | `Windsurf万法归宗/对话追踪/` | 每90s增量备份所有对话 |
| `dao_backup.py` | `Windsurf万法归宗/对话追踪/` | 全量备份/统计工具 |
| `dao_daemon.py` | `安全管理/` | 主守护：每2h触发dao_backup，管理dao_autosave进程 |
| `dao_ws_probe.py` | `安全管理/` | 探测本机+179备份状态，供security_hub调用 |

### 笔记本 (192.168.31.179)

| 组件 | 路径 | 作用 |
|------|------|------|
| `dao_autosave.py` | `D:\dao_autosave\` | 每90s增量备份179上的对话 |
| 计划任务 | `道之永存_Windsurf对话自动备份` | SYSTEM账户AtStartup+AtLogOn，5次自动重启 |

### 同步

```
本机 dao_autosave → 永存/ → git → GitHub
179  dao_autosave → D:\dao_autosave\永存\ (独立保存)

脚本更新: .\→双机同步.ps1          (WinRM将本机最新脚本推送至179)
状态查看: .\→双机同步.ps1 -Status
```

## 铁律

1. **R1**: Memory禁止存储实际密码/Token值
2. **R2**: git tracked文件禁止明文凭据
3. **R3**: 新增凭据必须同时更新 secrets.env + 凭据中心.md
4. **R4**: 修改凭据只改 secrets.env 一处
5. **R5**: Agent用HTTP API读凭据

## 启动

```bash
python 安全管理/dao_daemon.py        # 主守护 (管理所有子服务)
python 安全管理/security_hub.py      # Hub :9877 (单独启动)
# Dashboard: http://127.0.0.1:9877/
```
