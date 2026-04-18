# WAM · 无感切号

> **道法自然 · 反者道之动 · 太上不知有之**
> Windsurf Account Manager — 零感知多账号智能切换 · 自适应一切环境

[![Open VSX](https://img.shields.io/badge/open--vsx-v17.14.0-brightgreen)](https://open-vsx.org/extension/zhouyoukang/wam)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

## 核心能力

**智能切号** — 每次额度变动自动轮转到最优账号 (Claude 可用 + D/W 剩余最高 + 未冷却)
**多认证融合** — Firebase idToken (原生) + Devin sessionToken (Windsurf 新身份迁移)
**自适应运行时** — 根据实测 RTT × 错误率 × executeCommand 延迟, 13 项性能参数自动调优
**披褐怀玉 UI** — 单按钮 (意图开关), 功能全自动后台运行
**公网自动更新** — `wam.autoUpdate.source` 支持 HTTPS/SMB/本地路径
**跨会话持久化** — Firebase + Devin token 双缓存, 重启不丢学习状态

## 安装

### 从 Windsurf Extensions Marketplace (推荐)

1. 打开 Windsurf IDE
2. `Ctrl+Shift+X` 打开扩展面板
3. 搜索 `WAM` 或 `zhouyoukang.wam`
4. 点击 Install

### 从 .vsix 手动安装

```bash
windsurf --install-extension zhouyoukang.wam-17.14.0.vsix
```

## 快速开始

安装后打开 WAM 侧边栏:

1. **添加账号** — 点击 "+ 添加账号" 粘贴 `email:password` (支持批量多种分隔符)
2. **自动切号** — 默认开启, 额度变动自动轮转, 无需手动操作
3. **官方模式切换** — 点击 "🔑 官方登录" 暂停 WAM, 切回原生登录

## 自动更新 (公网闭环)

在 Windsurf `settings.json` 添加:

```jsonc
{
  // GitHub Releases 推荐源 · 任意公网用户可收新版本
  "wam.autoUpdate.source": "https://github.com/zhouyoukang/AGI/releases/latest/download/",
  "wam.autoUpdate.enabled": true,
  "wam.autoUpdate.intervalHours": 24
}
```

支持源类型:
- `https://...` — HTTPS 公网 (GitHub Releases / CDN)
- `\\\\host\\share\\bundle` — SMB 内网共享
- `D:\\path\\bundle` — 本地路径

## 设计哲学

### 太上不知有之 (十七章)
UI 上只有一个 `wam.autoRotate` 开关 · 用户无感而 WAM 无不为
- 验证清理 → 每 6h 自动 (`_startAutoVerify`)
- 有效期扫描 → 每 12h 自动 (`_startAutoExpiry`)
- 自动更新 → 每 24h 自动 (`_startAutoUpdate`)

### 反者道之动 (四十章)
性能参数不再硬编码, 而是逆流从实测数据学习:
- 网络 RTT p95 × 倍数 → 13 项超时/延迟自动调整 (`_adaptive`)
- executeCommand p95 × 1.5 → injectAuth 超时自学习 (`_injectAdaptive`)
- 慢网自动放大, 快网自动收缩

### 柔弱胜刚强 (三十六章)
Firebase → Devin fallback, 两套认证系统柔性融合:
- Firebase INVALID_LOGIN_CREDENTIALS → 自动尝试 Devin 登录
- Devin sessionToken 缓存 50min · 重复切号省 ~3000ms

### 披褐怀玉 (七十章)
外表极简 (一按钮), 内在丰富 (18 个命令 + 自适应算法):
- Ctrl+Shift+P 搜索 "WAM: ..." 可访问所有高级功能

## 性能基准 (v17.14)

| 场景 | 耗时 | 说明 |
|---|---|---|
| 首次 Devin 切号 | ~4500ms | Devin login + PostAuth + inject |
| 缓存命中 Devin 切号 | **~1500ms** | 直接 inject (省 ~3000ms) |
| Firebase 切号 | ~3000ms | cache HIT + inject |
| 冷启动自适应 | 8000ms 悲观默认 | 30 次样本后收敛 |

## 使用场景

- **个人多号管理** — 多个 Trial / Pro / Devin 账号池化
- **团队账号共享** — 通过 `accounts.json` 共享账号列表
- **跨机器自动同步** — `autoUpdate.source` 推送新版到所有机器

## 隐私 & 安全

- 账号密码仅存本地 `accounts.json` (未加密, 请妥善保管)
- Token 缓存 `~/.wam-hot/_token_cache.json` (50min TTL)
- 无遥测 · 无数据上报 · 仅与 Firebase/Windsurf 官方端点通信

## 反馈

- Issues: https://github.com/zhouyoukang/AGI/issues
- Discussions: https://github.com/zhouyoukang/AGI/discussions

## License

MIT © zhouyoukang

---

**道可道, 非常道 · 上善若水, 任方圆 · 功成而弗居**
