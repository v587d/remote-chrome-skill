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

### Prerequisites (read this first)

Before installing, ensure your environment has all of the following. Most Linux systems do NOT come with these by default.

| Component | Required version | How to verify / install |
|---|---|---|
| Windows 10/11 host with **Google Chrome** installed | Stable channel, Chrome v110+ recommended (requires `--remote-debugging-port` flag support and modern CDP) | Open Chrome, visit `chrome://version`; the "Google Chrome" line shows the version |
| **WSL 2** running Ubuntu (or any Linux subsystem that supports `/mnt/c/` mounts and a `nameserver` entry in `/etc/resolv.conf`) | WSL kernel 5.10+ recommended | PowerShell: `wsl --status`; inside WSL: `uname -r`. Older WSL1 (no real Linux kernel) and most other Linux-on-Windows subsystems do not expose `/mnt/c/` and will need the project edited to call `chrome.exe` differently |
| **Python 3.10+** available inside WSL | 3.10, 3.11, 3.12 all tested | `python3 --version`; if missing: `sudo apt install python3 python3-venv` (Ubuntu) |
| **uv** (Astral's Python package installer) installed inside WSL | Any recent version | `uv --version`; if missing: `curl -LsSf https://astral.sh/uv/install.sh | sh` |
| **Chrome DevTools Protocol reachable from WSL** | Configured by the bootstrap script | After running the bootstrap once (see below), verify with `uv run remote-chrome status` |

Notes for non-WSL Linux users:
- The CLI assumes two Windows-side paths by default: `C:\Program Files\Google\Chrome\Application\chrome.exe` and `C:\temp\chrome-debug-profile`. These two constants live in `src/remote_chrome/client.py` (`start_chrome`) and `scripts/windows-bootstrap.ps1`. If your Chrome is installed elsewhere, edit those two strings.
- `kill-chrome` uses PowerShell `Get-CimInstance` to filter by `--remote-debugging-port=9222`; it will not work from a non-Windows host.
- If you are running on a plain Linux box with Chrome locally installed, point `--host 127.0.0.1 --port 9222` to the Chrome instance and skip the `netsh portproxy` / `Get-CimInstance` steps.

### Architecture

```
WSL (this skill) ---> Windows IP:9223 ---> netsh portproxy ---> 127.0.0.1:9222 ---> Chrome
                       (HTTP /json + WS)                                    (--remote-debugging-port=9222)
```

### Install

```bash
git clone https://github.com/v587d/remote-chrome-skill.git
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

### Real-world session example (Gemini image generation, validated)

Below is a walkthrough from the actual test session (OpenCode + DeepSeek V4 Pro) that drove **Gemini's image generator end-to-end** from a WSL Ubuntu prompt. The user's full request was:

> 导航到 `https://gemini.google.com/app`，输入一段阿根廷对阵西班牙世界杯决赛的提示语，等待生成出图片，最后将图片下载至 cwd\image-material

The agent (after loading the `remote-chrome-skill`) executed this sequence as a single linear flow:

```text
T0  user prompt
    |
T1  uv run remote-chrome start-chrome
        -> { "started": true, "ready": true }                  # Chrome Debug bootstrapped from WSL via PowerShell Start-Process
    |
T2  uv run remote-chrome navigate "https://gemini.google.com/app" \
            --wait-for-selector "textarea, input[type=text], [contenteditable=true]" --timeout 60
        -> readyState hit, but SPA selector wait timed out    # Discovered: Gemini's compose box is a Quill <div>, not a <textarea>
        -> agent fell back to probing the DOM
    |
T3  uv run remote-chrome eval "JSON.stringify({title, url, bodyText: document.body.innerText.substring(0, 2000)})"
        -> confirmed logged in as "Hui", page rendered
    |
T4  uv run remote-chrome eval "(async () => {
          const inputs = document.querySelectorAll('textarea, input[type=text], [contenteditable=true], [role=textbox], .ql-editor, .ProseMirror');
          return JSON.stringify(Array.from(inputs).map((el, i) => ({i, tag, class, role, placeholder, visible, rect})));
        })()"
        -> found: div.ql-editor.textarea, role=textbox, placeholder="Ask Gemini"
    |
T5  uv run remote-chrome click ".ql-editor.textarea"           # focus the editor
        -> { x: 957.5, y: 122.8, selector: ".ql-editor.textarea" }
    |
T6  uv run remote-chrome type ".ql-editor.textarea" \
          "Generate a photorealistic image of the FIFA World Cup final between Argentina and Spain. ..."
        -> { input_value: "Generate a photorealistic image of the FIFA World Cup final ..." }
    |
T7  uv run remote-chrome eval "...enumerate visible <button> and [role=button] with aria-labels..."
        -> found button[aria-label='Send message'] at index 10
    |
T8  uv run remote-chrome click "button[aria-label='Send message']"
        -> { x, y, selector }
    |
T9  sleep 15 && uv run remote-chrome eval "...enumerate .model-response with .querySelectorAll('img')..."
        -> "Gemini said" appeared with 1 <img> but empty src / alt=" loading"
    |
T10 uv run remote-chrome eval "(async () => {
          await new Promise(r => setTimeout(r, 5000));     // let blob: URL populate
          const imgs = document.querySelectorAll('img');
          return JSON.stringify(... visible imgs with src, naturalWidth, naturalHeight, complete ...);
        })()" --timeout-ms 60000
        -> blob:https://gemini.google.com/<uuid>, 1024x559, alt=", AI generated", complete=true
    |
T11 uv run remote-chrome eval "(async () => {
          const img = document.querySelector('img[alt=\", AI generated\"]');
          const canvas = document.createElement('canvas');
          canvas.width = img.naturalWidth; canvas.height = img.naturalHeight;
          canvas.getContext('2d').drawImage(img, 0, 0);
          return JSON.stringify({ ok: true, format: 'png', width, height, base64: canvas.toDataURL('image/png').split(',')[1] });
        })()" --timeout-ms 60000
        -> base64 too large for stdout, full payload landed in tool-output file
    |
T12 python3 -c "import json, base64
        with open('/home/.../tool-output/tool_<id>', 'r') as f:
            data = json.loads(json.loads(f.read())['value'])
        open('image-material/argentina-vs-spain-worldcup-final.png','wb').write(base64.b64decode(data['base64']))"
        -> Saved 1.4 MB PNG, 1024x559

RESULT: image-material/argentina-vs-spain-worldcup-final.png written by the agent (no copy/paste, no manual upload).
```

Key skills demonstrated by this flow:

- **`start-chrome`** cold-starts Chrome Debug from WSL without touching the user's browser.
- **`navigate --wait-for-selector`** declares readiness criteria; on timeout the agent fell back to DOM inspection rather than guessing.
- **`eval "(async () => { ... })()"`** awaited a Promise internally — exactly the case the P0 fix enables.
- **`click -> type -> click -> eval-poll`** pattern matches how a human drives the page.
- **`--timeout-ms 60000`** override is needed for async IIFEs whose result is large (DOM canvas -> base64).
- Final **blob URL -> canvas -> dataURL -> base64 -> file** extraction is the canonical way to download from `<img src="blob:...">` because the blob: URL is only valid inside the page and is not fetchable from outside.

This is the full OpenCode session in two and a half minutes — readable end-to-end at: <https://opncd.ai/share/fpOjjatq>

### Tested with

The skill was developed and validated against the following stack:

- **AI agent**: OpenCode (v1.18.3) with DeepSeek V4 Pro as the reasoning model — this is the primary test target. The skill is registered through `~/.config/opencode/skills/remote-chrome-skill/SKILL.md` and invoked via `/remote-chrome-skill` slash command or natural-language triggers.
- **In principle any agent that supports the OpenCode `/skills` discovery mechanism** can use it. The skill is just a `SKILL.md` markdown instruction set plus a Python CLI — any agent that can:
  1. Read the SKILL.md instruction file from one of the standard skill discovery paths (`.opencode/skills/`, `~/.config/opencode/skills/`, `~/.claude/skills/`, `~/.agents/skills/` — see OpenCode's official skills docs), and
  2. Execute shell commands including `uv run remote-chrome ...`
  ...can use this skill. Concretely that means OpenCode, Claude Code (via `.claude/skills/`), and similar agent CLIs that consume the same skill markdown format.

Host platform:

- WSL 2 (Windows 11) running Ubuntu 24.04 LTS guest
- Windows host IP from inside WSL: `172.25.112.1`
- Windows host port forward: `netsh portproxy` 9223 → 127.0.0.1:9222
- Chrome version at test time: Chrome/150.0.7871.115 (Stable channel)
- Skill tested end-to-end against: Wikipedia (regression), example.com (sanity), Gemini Web App (real flow), X (SPAs / virtual lists; some issues still tracked in issues backlog)

The skills and quirks documented above (esp. the SPA scroll / async eval patterns) were discovered against this stack. Different hosts may need parameter tweaks but the protocol-level approach should apply anywhere CDP is reachable from the Linux side.

### Security

- The debug Chrome profile is **separate** from your main Chrome profile. Your main profile is never touched.
- This skill deliberately does NOT automate password entry. Type credentials yourself.
- Cookies returned by `remote-chrome cookies` are sensitive — do not paste them into chat logs.

### License and intended use

- Source code license: **MIT** — see `LICENSE`.
- **Intended use: learning and personal experimentation only.** This skill is published as a study of how an LLM agent can drive a real browser over CDP from a Linux guest. The author takes no responsibility for any commercial use of this code.
- **Commercial use is explicitly disallowed.** If you want to use this skill (or derivatives of it) in a commercial product or paid service, that is your decision and your sole responsibility — the skill author is not affiliated with and provides no warranty for such use. By using this skill you accept full liability for any downstream consequences.

---

## 中文

### 作用

一个 skill + Python CLI，让 AI agent（或你自己）从 WSL Ubuntu 里操控运行在 Windows 宿主机上的真实 Chrome。基于 Chrome DevTools Protocol over WebSocket。真实鼠标点击、真实键盘输入、真实 cookie 和 localStorage —— 没有 headless 仿真，没有第二个浏览器。

适用于需要真实已登录浏览器 profile 的场景：
- 用户手动登录后读取 auth cookie
- 在屏蔽 headless Chrome 的站点上做重复页面交互
- 让 AI 编程 agent（OpenCode 等）驱动真实浏览器会话

### 环境前置条件（请先确认）

装之前请确认下列环境就绪。多数 Linux 发行版**不会自带**以下任何项。

| 组件 | 要求版本 | 如何检查 / 安装 |
|---|---|---|
| **Windows 10/11 + Google Chrome** | 稳定版 Chrome，建议 v110+（需支持 `--remote-debugging-port` 与新版 CDP） | Chrome 里访问 `chrome://version`，「Google Chrome」一行即版本 |
| **WSL 2 + Ubuntu**（或任一支持 `/mnt/c/` 挂载、且 `/etc/resolv.conf` 有 `nameserver` 项的 Linux 子系统） | WSL 内核 5.10+ 推荐 | PowerShell 里 `wsl --status`；WSL 内 `uname -r`。老的 WSL1（非真 Linux 内核）以及多数其它 Windows-on-Linux 子系统不会暴露 `/mnt/c/`，需自行改 `chrome.exe` 调用路径 |
| **WSL 内的 Python** | 3.10 / 3.11 / 3.12 都已测过 | `python3 --version`；缺失时执行：`sudo apt install python3 python3-venv`（Ubuntu） |
| **uv**（Astral 出的 Python 包管理器） | 任意较新版本 | `uv --version`；缺失时执行：`curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **CDP 从 WSL 可达** | 通过 bootstrap 脚本一次性配置 | 跑完下面的 bootstrap 后，用 `uv run remote-chrome status` 验证 |

非 WSL Linux 用户额外注意：
- CLI 默认假设两处 Windows 路径：`C:\Program Files\Google\Chrome\Application\chrome.exe` 与 `C:\temp\chrome-debug-profile`，写死在 `src/remote_chrome/client.py` 的 `start_chrome` 与 `scripts/windows-bootstrap.ps1`。如 Chrome 装在别处，改这两处即可。
- `kill-chrome` 用 PowerShell `Get-CimInstance` 按 `--remote-debugging-port=9222` 过滤；非 Windows 主机不可用。
- 如果你是在原生 Linux 主机上、Chrome 就在该主机本地，可直接 `uv run remote-chrome --host 127.0.0.1 --port 9222 <cmd>` 直连本地 Chrome，跳过 `netsh portproxy` 与 `Get-CimInstance` 步骤。

### 架构

```
WSL (本 skill) ---> Windows IP:9223 ---> netsh portproxy ---> 127.0.0.1:9222 ---> Chrome
                    (HTTP /json + WS)                                    (--remote-debugging-port=9222)
```

### 安装

```bash
git clone https://github.com/v587d/remote-chrome-skill.git
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

### 真实使用流程示例（Gemini 生图，已实测）

下面是一次完整实测流程的 walkthrough（OpenCode + DeepSeek V4 Pro），agent 在 WSL Ubuntu 一行花两分半钟就跑完了。用户原始请求：

> 导航到 `https://gemini.google.com/app`，输入一段阿根廷对阵西班牙世界杯决赛的提示语，等待生成出图片，最后将图片下载至 cwd\image-material

agent 加载 `remote-chrome-skill` 后，按下述线性流程执行：

```text
T0  用户 prompt
    |
T1  uv run remote-chrome start-chrome
        -> { "started": true, "ready": true }                  # 从 WSL 经 PowerShell Start-Process 拉起 Chrome Debug
    |
T2  uv run remote-chrome navigate "https://gemini.google.com/app" \
            --wait-for-selector "textarea, input[type=text], [contenteditable=true]" --timeout 60
        -> readyState 满足，但 selector 等超时                 # 因此排查：Gemini 的输入框其实是 Quill <div>，不是 <textarea>
    |
T3  uv run remote-chrome eval "JSON.stringify({title, url, bodyText: document.body.innerText.substring(0, 2000)})"
        -> 看到已登录为 "Hui"、页面已渲染
    |
T4  uv run remote-chrome eval "(async () => {
          const inputs = document.querySelectorAll('textarea, input[type=text], [contenteditable=true], [role=textbox], .ql-editor, .ProseMirror');
          return JSON.stringify(Array.from(inputs).map((el, i) => ({i, tag, class, role, placeholder, visible, rect})));
        })()"
        -> 命中：div.ql-editor.textarea，role=textbox，placeholder="Ask Gemini"
    |
T5  uv run remote-chrome click ".ql-editor.textarea"           # 聚焦编辑器
        -> { x: 957.5, y: 122.8, selector: ".ql-editor.textarea" }
    |
T6  uv run remote-chrome type ".ql-editor.textarea" \
          "Generate a photorealistic image of the FIFA World Cup final between Argentina and Spain. ..."
        -> { input_value: "Generate a photorealistic image of the FIFA World Cup final ..." }
    |
T7  uv run remote-chrome eval "...enumerate visible <button> and [role=button] with aria-labels..."
        -> 在 index 10 找到 button[aria-label='Send message']
    |
T8  uv run remote-chrome click "button[aria-label='Send message']"
        -> { x, y, selector }
    |
T9  sleep 15 && uv run remote-chrome eval "...用 .model-response 查 .querySelectorAll('img')..."
        -> 出现 "Gemini said"，1 张 <img> 但 src 空 / alt=" loading"
    |
T10 uv run remote-chrome eval "(async () => {
          await new Promise(r => setTimeout(r, 5000));     // 等 blob: URL 真的填上
          const imgs = document.querySelectorAll('img');
          return JSON.stringify(... 可见 imgs 的 src/naturalWidth/naturalHeight/complete ...);
        })()" --timeout-ms 60000
        -> blob:https://gemini.google.com/<uuid>，1024×559，alt=", AI generated"，complete=true
    |
T11 uv run remote-chrome eval "(async () => {
          const img = document.querySelector('img[alt=\", AI generated\"]');
          const canvas = document.createElement('canvas');
          canvas.width = img.naturalWidth; canvas.height = img.naturalHeight;
          canvas.getContext('2d').drawImage(img, 0, 0);
          return JSON.stringify({ ok: true, format: 'png', width, height, base64: canvas.toDataURL('image/png').split(',')[1] });
        })()" --timeout-ms 60000
        -> base64 较大被工具截断，但完整 payload 自动落到 tool-output 文件
    |
T12 python3 -c "import json, base64
        with open('/home/.../tool-output/tool_<id>', 'r') as f:
            data = json.loads(json.loads(f.read())['value'])
        open('image-material/argentina-vs-spain-worldcup-final.png','wb').write(base64.b64decode(data['base64']))"
        -> 写出 1.4 MB PNG，1024x559

结果：image-material/argentina-vs-spain-worldcup-final.png 被 agent 自己保存好（全程无手动复制粘贴、无手动上传）。
```

本流程展示的能力：

- **`start-chrome`** 从 WSL 冷启动 Chrome Debug 实例，不碰用户主浏览器。
- **`navigate --wait-for-selector`** 主动声明就绪标准；超时回落到 DOM 排查而非硬猜 selector。
- **`eval "(async () => { ... })()"`** 内部 await Promise —— 正是 P0 修复才支持的写法。
- **`click -> type -> click -> eval-poll`** 是与人手操作一致的流程组合。
- **`--timeout-ms 60000`** 对返回大 base64 的 async IIFE 必须调高。
- 最终的 **blob URL -> canvas -> dataURL -> base64 -> 落盘** 是 `<img src="blob:...">` 下载的唯一稳妥姿势 —— blob: URL 仅在页面内有效，外部任何 fetch 都拿不到。

完整会话（共 2 分 27 秒）：https://opncd.ai/share/fpOjjatq

### 在哪些 Agent 中已验证

本 skill 的开发与回归测试在下列栈上完成：

- **AI agent**：OpenCode（v1.18.3），推理模型 DeepSeek V4 Pro —— 主测试目标。skill 经 `~/.config/opencode/skills/remote-chrome-skill/SKILL.md` 注册，可用 `/remote-chrome-skill` slash 命令或自然语言触发词调用。
- **理论上所有支持 OpenCode `/skills` 发现机制的 Agent 通用。** skill 本体只是一份 `SKILL.md` 指令 + 一个 Python CLI —— 任何 Agent 只要：
  1. 从标准 skill 发现路径之一（`.opencode/skills/`、`~/.config/opencode/skills/`、`~/.claude/skills/`、`~/.agents/skills/`，详见 OpenCode 官方 skills 文档）读取 `SKILL.md`；且
  2. 能执行 shell 命令，包含 `uv run remote-chrome ...`
  …… 都能用这个 skill。具体而言包含 OpenCode、Claude Code（通过 `.claude/skills/`）以及其他消费相同 skill markdown 格式的 agent CLI。

主机平台：

- WSL 2（Windows 11）+ Ubuntu 24.04 LTS 客机
- WSL 内看到的 Windows 主机 IP：`172.25.112.1`
- Windows 主机端口转发：`netsh portproxy` 9223 → 127.0.0.1:9222
- 测试时 Chrome 版本：Chrome/150.0.7871.115（Stable 通道）
- 端到端验证过的站点：Wikipedia（回归）、example.com（弹点测试）、Gemini Web App（真实流程）、X（SPA / 虚拟列表；部分 issues 仍在修）

上面那些 SPA scroll / async eval 等 pattern，就是在这一套栈上踩出来的。不同主机可能要调几个参数，但协议层思路在任意 CDP 可达 Linux 端都通。

### 安全

- debug Chrome 的 profile 与你主 Chrome 的 profile **完全独立**，主 profile 永远不会被触碰。
- 本 skill 故意不做密码自动输入，凭据必须由用户手工输入。
- `remote-chrome cookies` 返回的 cookie 是敏感数据，不要粘贴到聊天/日志里。

### 许可证与使用范围

- 源码许可：**MIT** —— 见 `LICENSE`。
- **本 skill 仅用于学习与个人实验。** 作者不承担任何由使用本 skill 产生的直接或间接责任。
- **禁止商用。** 若你希望将本 skill（或其衍生物）用于商业产品或付费服务，那是你的决定与你的全部责任 —— skill 作者与任何商用无关、不为商用提供担保。使用即代表你接受全部下游法律与技术责任。

