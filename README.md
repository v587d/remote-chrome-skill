# remote-chrome-skill

> Control a **real Chrome** on Windows from WSL Ubuntu — via Chrome DevTools Protocol (CDP).
> A skill + Python CLI that lets an AI agent drive your actual Chrome: real clicks, real keyboard input, real cookies/localStorage, no headless emulation.

English | [中文](#中文)

---

<!-- Demo video uploaded via GitHub issue attachments (free plan 10MB limit). -->
<p align="center">
  <video src="https://github.com/user-attachments/assets/8461c2a6-d521-4f8b-89f4-8fbee44419fb" width="640" controls muted></video>
</p>

## What it does

- **Drive real Chrome** — real mouse clicks, real keyboard, real cookies/localStorage. Not headless.
- **SPA-ready** — `--wait-for-selector` / `--wait-for-title` / async eval polling for dynamic pages.
- **Event-driven** — subscribe to console logs, network, DOM mutations, page lifecycle.
- **Network monitoring** — filter by URL/resource-type, retrieve request/response details.
- **Secure by default** — separate debug profile, no password automation, selective kill.

Full command reference: [`references/api.md`](references/api.md)

---

## Prerequisites (read before install)

To install **100% successfully**, confirm these **before** running any install command:

| # | Requirement | How to verify |
|---|-------------|---------------|
| 1 | **Windows 10/11** with **Google Chrome** installed | Open Chrome on Windows once |
| 2 | **WSL 2** with **Ubuntu** | `wsl -l -v` in PowerShell shows `Ubuntu` version `2` |
| 3 | **Python 3.10+** inside WSL | `python3 --version` → `3.10` or higher |
| 4 | **[uv](https://astral.sh/uv)** installed inside WSL | `uv --version` works |
| 5 | **Pi Agent** already running | `pi --version` works |

If any check fails, fix it before installing — the skill cannot work without all five.

> **Python 3.10:** install with `sudo apt install python3` (Ubuntu 22.04+ already meets this).
> **uv:** install with `curl -LsSf https://astral.sh/uv/install.sh | sh`.

---

## Install (Pi Agent users)

```bash
# 1. Install the skill as a Pi package
pi install git:github.com/v587d/remote-chrome-skill

# 2. Install Python dependencies
cd ~/.pi/agent/git/github.com/v587d/remote-chrome-skill
uv sync
```

That's it for the WSL side. Skip to **Windows one-time setup** below.

<details>
<summary>Alternatively: install a pinned version / branch</summary>

```bash
# Pin to a tag (recommended for reproducibility)
pi install git:github.com/v587d/remote-chrome-skill@v0.1.0

# Or clone manually without Pi
git clone https://github.com/v587d/remote-chrome-skill.git
cd remote-chrome-skill && uv sync
```

</details>

---

## Windows one-time setup (run as Administrator)

The WSL side cannot reach Chrome yet — you must configure port forwarding + firewall **once** on Windows.

```powershell
# 1. In WSL, print the bootstrap script:
uv run remote-chrome bootstrap

# 2. Copy the printed PowerShell script.

# 3. Open PowerShell **as Administrator** on Windows and paste it.
#    This sets up netsh portproxy + a firewall rule for WSL → Chrome:9223.
#    Persists across reboots.
```

This only needs to be done once per Windows machine.

---

## Use it

### From a shell

```bash
uv run remote-chrome start-chrome                          # Launch debug Chrome on Windows
uv run remote-chrome navigate "https://example.com"        # SPA-aware --wait-for-selector supported
uv run remote-chrome click "#submit"
uv run remote-chrome type "#input" "hello"
uv run remote-chrome cookies                               # Read cookies (current origin by default)
uv run remote-chrome screenshot --format png               # Viewport or full-page
uv run remote-chrome event subscribe Runtime.consoleAPICalled   # Subscribe to CDP events
```

### From Pi Agent

Just say it naturally — the skill loads automatically:

> open browser search pi agent and return first 3 results

That's it. Pi routes the request to this skill's `remote-chrome` CLI.

---

## Security

- The debug Chrome runs on a **separate profile** — never touches your personal browsing data.
- This skill does **NOT** automate password entry — use `wait-for-auth` to pause for manual login.
- `kill-chrome` kills only the debug instance, never your regular Chrome.

---

## License

MIT — see [LICENSE](LICENSE).

---

## 中文

### 是什么

一个 skill + Python CLI，让 AI agent 从 WSL Ubuntu 里操控 Windows 上的**真实 Chrome**。基于 CDP 协议：真实的鼠标点击、键盘输入、Cookie 和 localStorage，不使用 headless 模拟。

核心能力：跨虚拟列表的 `mouseWheel` 滚动、SPA `--wait-for-selector` 等待、CDP 事件订阅（console / network / DOM / page lifecycle）、网络请求监控、截图、origin 级别的 cookie 读取。

### 安装前必须确认（缺一不可，否则一定装不上）

| 序号 | 条件 | 验证方式 |
|------|------|----------|
| 1 | **Windows 10/11** 且已安装 **Chrome** | 在 Windows 打开过 Chrome |
| 2 | **WSL 2** 中运行着 **Ubuntu** | PowerShell 跑 `wsl -l -v` 看到 `Ubuntu` 版本 `2` |
| 3 | WSL 里安装了 **Python 3.10+** | `python3 --version` ≥ `3.10` |
| 4 | WSL 里安装了 **[uv](https://astral.sh/uv)** | `uv --version` 能输出 |
| 5 | 已经在用 **Pi Agent** | `pi --version` 能输出 |

全绿了再往下走。

> 没装 Python：`sudo apt install python3`（Ubuntu 22.04+ 自带满足）。
> 没装 uv：`curl -LsSf https://astral.sh/uv/install.sh | sh`。

### 安装（Pi Agent 用户）

```bash
# 1. 以 Pi 包形式安装
pi install git:github.com/v587d/remote-chrome-skill

# 2. 安装 Python 依赖
cd ~/.pi/agent/git/github.com/v587d/remote-chrome-skill
uv sync
```

<details>
<summary>其它安装方式</summary>

```bash
# 钉到某个 tag（推荐用于复现）
pi install git:github.com/v587d/remote-chrome-skill@v0.1.0

# 或不用 Pi，直接手动 clone
git clone https://github.com/v587d/remote-chrome-skill.git
cd remote-chrome-skill && uv sync
```

</details>

### Windows 一次性配置（管理员身份）

WSL 这侧装好后还连不到 Chrome，需要在 Windows 上**一次性**配置端口转发 + 防火墙：

```powershell
# 1. 在 WSL 里打印引导脚本：
uv run remote-chrome bootstrap

# 2. 复制打印出来的 PowerShell 脚本。

# 3. 在 Windows 以管理员身份打开 PowerShell，粘贴运行。
#    会建立 netsh portproxy + 防火墙规则，让 WSL 能访问 Chrome:9223。
#    重启后依然有效。
```

每台 Windows 机器只需做一次。

### 使用

命令行：

```bash
uv run remote-chrome start-chrome
uv run remote-chrome navigate "https://example.com"
uv run remote-chrome click "#按钮"
uv run remote-chrome type "#输入框" "你好"
uv run remote-chrome cookies
uv run remote-chrome screenshot --format png
uv run remote-chrome event subscribe Runtime.consoleAPICalled
```

在 Pi Agent 里直接用自然语言说，skill 会自动加载：

> 打开浏览器搜索 pi agent 并返回前三条

### 安全

- 调试 Chrome 用独立 profile，不碰你日常浏览的数据。
- 本 skill **不会**自动输入密码，登录用 `wait-for-auth` 手动完成。
- `kill-chrome` 只杀调试实例，绝不杀你日常用的 Chrome。

### 协议

MIT — 见 [LICENSE](LICENSE)。