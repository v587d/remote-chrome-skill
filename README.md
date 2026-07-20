# remote-chrome-skill

> Control a Chrome browser running on Windows from WSL Ubuntu. Via OpenCode skill or as a standalone CLI.

[English](#english) | [中文](#中文)

---

## English

### What it does

A skill + Python CLI that lets an AI agent (or you) drive a real Chrome running on the Windows host from inside WSL Ubuntu. Chrome DevTools Protocol over WebSocket. Real mouse clicks, real keyboard input, real cookies and localStorage — no headless emulation, no separate browser.

It is designed for scenarios where you need a real logged-in browser profile:
- Reading auth cookies after the user logs in manually
- Automating repetitive page interactions on sites that block headless Chrome
- Driving a real browser session from an AI coding agent (OpenCode, etc.)

### Architecture

```
WSL (this skill) ---> Windows IP:9223 ---> netsh portproxy ---> 127.0.0.1:9222 ---> Chrome
                       (HTTP /json + WS)                                    (--remote-debugging-port=9222)
```

### Install

```bash
git clone https://github.com/<owner>/remote-chrome-skill
cd remote-chrome-skill
uv sync                    # creates .venv, installs websockets
```

### One-time Windows setup

Run as Administrator PowerShell on Windows:

```powershell
# Either copy and paste scripts/windows-bootstrap.ps1 contents
# Or run it directly:
powershell -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu\home\<you>\projects\remote-chrome-skill\scripts\windows-bootstrap.ps1
```

This configures:
1. `netsh portproxy` rule: `0.0.0.0:9223` -> `127.0.0.1:9222`
2. Firewall rule allowing TCP 9223 inbound from WSL subnet
3. `C:\temp\chrome-debug-profile` directory
4. Desktop shortcut "Chrome Debug"

The setup persists across reboots.

### Usage

```bash
# Start Chrome (or just double-click the "Chrome Debug" desktop shortcut)
uv run remote-chrome start-chrome

# Check it is reachable
uv run remote-chrome status

# List tabs
uv run remote-chrome list-tabs

# Navigate, click, type, scroll
uv run remote-chrome navigate "https://www.wikipedia.org/"
uv run remote-chrome click "#searchInput"
uv run remote-chrome type "#searchInput" "OpenCode"
uv run remote-chrome scroll --dy 500            # default method=wheel (real mouse wheel events)
uv run remote-chrome scroll --dy 1500 --wait-ms 500    # scroll, then wait for async renders

# For SPA sites (X, Reddit) where readyState lies, wait for a selector or title:
uv run remote-chrome navigate "https://x.com/" --wait-for-selector "article"

# Read data
uv run remote-chrome cookies                    # default = current page origin only
uv run remote-chrome cookies --domain google.com    # explicit domain filter
uv run remote-chrome cookies --all                  # entire browser cookie jar
uv run remote-chrome localstorage
uv run remote-chrome eval "document.title"

# Async eval works out of the box (awaits Promises by default):
uv run remote-chrome eval "(async () => { return 'awaited-async'; })()"
uv run remote-chrome eval "(async () => { ... })()" --timeout-ms 60000   # override default 30s

# Login flow (you type credentials in the real Chrome window, the agent waits)
uv run remote-chrome navigate "https://accounts.google.com/" --wait-for-selector "input[type=email]"
# Tell the user to type email/password/2FA in the Chrome window
uv run remote-chrome wait-for-auth --cookie-name SID --cookie-domain .google.com --timeout 300
uv run remote-chrome cookies --domain google.com
```

### Using as an OpenCode skill

Clone (or symlink) this repo into your project so that `.opencode/skills/remote-chrome-skill/SKILL.md` is discoverable from your project root. Then any agent that calls the `skill` tool can load it.

### Handling SPAs (X, Reddit, modern e-commerce)

These sites render their UI AFTER `document.readyState==='complete'`. Use one of these waits instead of (or in addition to) the default readyState wait:

```bash
uv run remote-chrome navigate "https://x.com/" --wait-for-selector "article"
uv run remote-chrome navigate "https://x.com/home" --wait-for-title "Home"
```

For scrolling on virtualized lists (X, Reddit), the default `--method=wheel` dispatches real CDP "mouseWheel" events — required because these sites listen for wheel events, not just scroll position. Use `--wait-ms` to let renders settle:

```bash
uv run remote-chrome scroll --dy 1500 --wait-ms 500
```

Async IIFEs await Promises by default, so you can poll for DOM stability in one CLI call:

```bash
uv run remote-chrome eval "(async () => {
  let prev = -1, stable = 0;
  for (let i = 0; i < 30; i++) {
    const n = document.querySelectorAll('article').length;
    if (n === prev && n > 0) { stable++; if (stable >= 4) return {stabilized: true, count: n}; }
    else { stable = 0; }
    prev = n;
    await new Promise(r => setTimeout(r, 200));
  }
  return {stabilized: false, last_count: prev};
})()"
```

### Security

- The debug Chrome profile is **separate** from your main Chrome profile. Your main profile is never touched.
- This skill deliberately does NOT automate password entry. Type credentials yourself.
- Cookies returned by `remote-chrome cookies` are sensitive — do not paste them into chat logs.

### License

MIT — see `LICENSE`.

---

## 中文

### 作用

一个 skill + Python CLI，让 AI agent（或你自己）从 WSL Ubuntu 里操控运行在 Windows 宿主机上的真实 Chrome。基于 Chrome DevTools Protocol over WebSocket。真实鼠标点击、真实键盘输入、真实 cookie 和 localStorage —— 没有 headless 仿真，没有第二个浏览器。

适用于需要真实已登录浏览器 profile 的场景：
- 用户手动登录后读取 auth cookie
- 在屏蔽 headless Chrome 的站点上做重复页面交互
- 让 AI 编程 agent（OpenCode 等）驱动真实浏览器会话

### 架构

```
WSL (本 skill) ---> Windows IP:9223 ---> netsh portproxy ---> 127.0.0.1:9222 ---> Chrome
                    (HTTP /json + WS)                                    (--remote-debugging-port=9222)
```

### 安装

```bash
git clone https://github.com/<owner>/remote-chrome-skill
cd remote-chrome-skill
uv sync                    # 创建 .venv，安装 websockets
```

### Windows 一次性配置

在 **以管理员身份启动的 PowerShell** 中执行（复制粘贴或运行脚本）：

```powershell
# 方式一：复制 scripts/windows-bootstrap.ps1 内容粘贴到 PowerShell
# 方式二：直接运行
powershell -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu\home\<你>\projects\remote-chrome-skill\scripts\windows-bootstrap.ps1
```

配置 4 件事：
1. `netsh portproxy` 规则：`0.0.0.0:9223 -> 127.0.0.1:9222`
2. 防火墙规则：放行 WSL 子网 TCP 9223 入站
3. `C:\temp\chrome-debug-profile` 目录
4. 桌面快捷方式「Chrome Debug」

重启后配置仍然保留。

### 使用

```bash
# 启动 Chrome（或直接双击桌面「Chrome Debug」快捷方式）
uv run remote-chrome start-chrome

# 检查可达性
uv run remote-chrome status

# 列出标签页
uv run remote-chrome list-tabs

# 导航、点击、输入、滚动
uv run remote-chrome navigate "https://www.wikipedia.org/"
uv run remote-chrome click "#searchInput"
uv run remote-chrome type "#searchInput" "OpenCode"
uv run remote-chrome scroll --dy 500            # 默认 method=wheel，发送真实鼠标滚轮事件
uv run remote-chrome scroll --dy 1500 --wait-ms 500    # 滚 + 等 500ms 让异步渲染完成

# SPA 站点（X / Reddit 等）的 readyState 不可靠，用 selector/title 校验：
uv run remote-chrome navigate "https://x.com/" --wait-for-selector "article"

# 读取数据
uv run remote-chrome cookies                    # 默认只返回当前页 origin 的 cookie
uv run remote-chrome cookies --domain google.com    # 显式过滤域
uv run remote-chrome cookies --all                  # 整个浏览器 cookie jar
uv run remote-chrome localstorage
uv run remote-chrome eval "document.title"

# async eval 直接可工作（默认 await Promise）：
uv run remote-chrome eval "(async () => { return 'awaited-async'; })()"
uv run remote-chrome eval "(async () => { ... })()" --timeout-ms 60000   # 覆盖默认 30s

# 登录场景（你在真实 Chrome 窗口手动输入凭据，agent 等待）
uv run remote-chrome navigate "https://accounts.google.com/" --wait-for-selector "input[type=email]"
# 告诉用户在 Chrome 窗口里输入邮箱/密码/2FA
uv run remote-chrome wait-for-auth --cookie-name SID --cookie-domain .google.com --timeout 300
uv run remote-chrome cookies --domain google.com
```

### 处理 SPA（X / Reddit / 现代电商）

这些站点在 `document.readyState==='complete'` 后才开始渲染 UI。除了默认 readyState 等，可以用下面方式等真正的就绪：

```bash
uv run remote-chrome navigate "https://x.com/" --wait-for-selector "article"
uv run remote-chrome navigate "https://x.com/home" --wait-for-title "Home"
```

虚拟列表的滚动（X / Reddit 等），默认 `--method=wheel` 发送真实 CDP `mouseWheel` 事件 —— 这是必需的，因为这类站点看 `wheel` 事件而非仅看 scroll position。用 `--wait-ms` 等渲染完成：

```bash
uv run remote-chrome scroll --dy 1500 --wait-ms 500
```

async eval 默认就 await Promise，可以用一次 CLI 调用轮询 DOM 稳定：

```bash
uv run remote-chrome eval "(async () => {
  let prev = -1, stable = 0;
  for (let i = 0; i < 30; i++) {
    const n = document.querySelectorAll('article').length;
    if (n === prev && n > 0) { stable++; if (stable >= 4) return {stabilized: true, count: n}; }
    else { stable = 0; }
    prev = n;
    await new Promise(r => setTimeout(r, 200));
  }
  return {stabilized: false, last_count: prev};
})()"
```

### 作为 OpenCode skill 使用

把这个仓库 clone（或软链接）到你的项目里，让 `.opencode/skills/remote-chrome-skill/SKILL.md` 能从项目根被向上扫到。任何调用 `skill` 工具的 agent 都能加载。

### 安全

- debug Chrome 的 profile 与你主 Chrome 的 profile **完全独立**，主 profile 永远不会被触碰。
- 本 skill 故意不做密码自动输入，凭据必须由用户手工输入。
- `remote-chrome cookies` 返回的 cookie 是敏感数据，不要粘贴到聊天/日志里。

### License

MIT — 见 `LICENSE`。

