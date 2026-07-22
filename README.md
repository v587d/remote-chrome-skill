# remote-chrome-skill

> Control a **real Chrome** browser running on Windows from WSL Ubuntu — via Chrome DevTools Protocol (CDP).

A skill + Python CLI that lets an AI agent drive your actual Chrome browser. Real mouse clicks, real keyboard input, real cookies and localStorage — no headless emulation.

English | [中文](#中文)

---

## Prerequisites

- Windows 10/11 with Google Chrome installed
- WSL 2 running Ubuntu
- Python 3.10+ and [uv](https://astral.sh/uv) inside WSL

---

## Install

```bash
# For Pi Agent users — install as a package
pi install git:github.com/v587d/remote-chrome-skill

# Then install Python dependencies
cd ~/.pi/agent/git/github.com/v587d/remote-chrome-skill
uv sync

# Or clone manually
git clone https://github.com/v587d/remote-chrome-skill.git 
cd remote-chrome-skill && uv sync
```

────────────────────────────────────────────────────────────────────────────────

Windows Setup (one-time, run as Administrator)

```powershell
# Print the bootstrap script from WSL, then paste into an Admin PowerShell on Windows:
uv run remote-chrome bootstrap
```

This configures port forwarding and firewall — persists across reboots.

────────────────────────────────────────────────────────────────────────────────

Usage

```bash
uv run remote-chrome start-chrome         # Launch Chrome debug instance
uv run remote-chrome navigate "https://example.com"
uv run remote-chrome click "#submit"
uv run remote-chrome type "#input" "hello"
uv run remote-chrome cookies              # Read cookies (current page only)
uv run remote-chrome screenshot --format png
```

In Pi Agent, just say: open google.com and search for X — the skill loads automatically.

────────────────────────────────────────────────────────────────────────────────

Security

- The debug Chrome profile is separate from your main profile — never touches your personal browsing data
- This skill does NOT automate password entry — use wait-for-auth to wait for manual login
- kill-chrome kills only the debug instance, never your regular Chrome

────────────────────────────────────────────────────────────────────────────────

License

MIT — see LICENSE.

────────────────────────────────────────────────────────────────────────────────

中文

### 是什么

一个 skill + Python CLI，让 AI agent 从 WSL Ubuntu 里操控 Windows 上的真实 Chrome 浏览器。基于 CDP 协议，真实的鼠标点击、键盘输入、Cookie 和 localStorage，不用 headless 模拟。

### 安装

```bash
# Pi Agent 用户
pi install git:github.com/v587d/remote-chrome-skill
cd ~/.pi/agent/git/github.com/v587d/remote-chrome-skill && uv sync

# 手动 clone
git clone https://github.com/v587d/remote-chrome-skill.git 
cd remote-chrome-skill && uv sync
```

### Windows 一次性配置

在 Windows 管理员 PowerShell 中运行 `uv run remote-chrome bootstrap` 输出的脚本。

### 使用

```bash
uv run remote-chrome start-chrome
uv run remote-chrome navigate "https://example.com"
uv run remote-chrome click "#按钮"
uv run remote-chrome type "#输入框" "你好"
uv run remote-chrome cookies
uv run remote-chrome screenshot --format png
```

Pi Agent 中直接说「打开谷歌搜 XXX」就行，skill 自动加载。
