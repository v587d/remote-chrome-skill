# Remote Chrome Skill - 开发路线图

本文档记录了 remote-chrome-skill 的待办事项和改进建议，按优先级排序。

---

## P1 重要增强 (High Priority)

### 4. 网络请求监控
- **目标**: 实现对页面网络请求的拦截、监控和日志记录
- **场景**: 调试 SPA 应用、抓取 API 响应数据、分析资源加载
- **技术点**: 
  - `Network.enable` / `Network.requestWillBeSent` / `Network.responseReceived`
  - 支持按 URL 过滤、按类型过滤 (XHR/Fetch/WS)
  - 获取请求头、响应头、响应体
- **输出格式**: JSON 数组，包含 requestId, url, method, status, timing 等字段

### 5. Tab 管理（新建/关闭）
- **目标**: 支持多标签页操作
- **场景**: 同时打开多个页面、后台预加载、清理无用标签
- **技术点**:
  - `Target.createTarget` (新建 tab)
  - `Target.closeTarget` (关闭 tab)
  - `Target.getTargets` (列出所有 tab)
  - `Target.attachToTarget` (切换到指定 tab)
- **命令设计**: `tab new`, `tab close`, `tab list`, `tab switch <id>`

### 6. CDP 事件订阅
- **目标**: 支持事件驱动模式，监听浏览器事件
- **场景**: 等待特定元素出现、监听控制台日志、捕获页面错误
- **技术点**:
  - 实现事件订阅/取消订阅机制
  - 支持 `Runtime.consoleAPICalled`, `Page.loadEventFired`, `DOM.attributeModified` 等
  - 异步事件回调或轮询接口
- **命令设计**: `event subscribe <eventType>`, `event unsubscribe`, `event poll`

### 7. 类型注解不完整
- **目标**: 为所有 Python 文件添加完整的类型注解
- **范围**: `client.py`, `cli.py`
- **工具**: 使用 `mypy` 进行类型检查
- **收益**: 提升代码可维护性，便于 IDE 自动补全和错误检测

---

## P2 用户体验 (Medium Priority)

### 8. SKILL.md 缺少用例模板
- **目标**: 在 SKILL.md 中添加常见场景的快速参考模板
- **内容**:
  - 单页应用数据抓取流程
  - 登录 + 操作 + 截图完整示例
  - 错误处理最佳实践
  - Prompt 编写技巧（如何描述复杂操作）

### 9. 错误信息可更结构化
- **目标**: 统一错误输出格式，便于 Agent 解析和处理
- **当前问题**: 错误信息分散在 traceback 中，Agent 难以提取关键信息
- **改进方案**:
  - 定义标准错误码 (如 `ERR_NAVIGATION_TIMEOUT`, `ERR_ELEMENT_NOT_FOUND`)
  - JSON 输出包含 `error_code`, `error_message`, `suggestion` 字段
  - 区分用户错误 vs 系统错误

### 10. status 命令诊断信息不足
- **目标**: 增强 `status` 命令的诊断能力
- **新增信息**:
  - Chrome 版本、协议版本
  - 当前连接的目标信息 (title, url)
  - 网络延迟统计
  - 内存使用情况 (如果可用)
  - 最近错误日志摘要

---

## P3 扩展性 (Future Enhancements)

### 11. 会话持久化
- **目标**: 支持保存和恢复浏览器会话状态
- **场景**: 长时间任务中断后恢复、跨会话复用登录状态
- **技术点**:
  - 序列化 Cookie + LocalStorage + SessionStorage
  - 保存当前 URL 和历史记录
  - `session save <name>`, `session load <name>`, `session list`

### 12. Headless 模式支持
- **目标**: 支持在无头模式下运行 Chrome
- **场景**: CI/CD 环境、服务器部署、减少资源占用
- **技术点**:
  - 启动参数 `--headless=new`
  - 处理 headless 模式下的特殊行为（如字体渲染差异）
  - 可选：支持无头模式的截图/PDF 生成优化

### 13. 多实例支持
- **目标**: 支持同时连接多个 Chrome 实例
- **场景**: 并行执行多个任务、隔离不同用户的浏览上下文
- **技术点**:
  - 通过 `--port` 或 `--instance-id` 区分实例
  - 连接池支持多实例管理
  - CLI 增加 `--instance` 参数

---

## P4 安全 (Security)

### 14. Cookie 自动脱敏
- **目标**: 在输出中自动脱敏敏感 Cookie 值
- **场景**: 防止 session token、auth cookie 泄露到日志或 Agent 上下文
- **技术点**:
  - 识别敏感 Cookie 名称 (如 `session`, `token`, `auth`, `jwt`)
  - 脱敏策略：仅显示前 4 位 + `***` + 后 4 位
  - 可配置脱敏规则

### 15. 操作审计日志
- **目标**: 记录所有浏览器操作的审计日志
- **场景**: 安全审计、问题排查、合规要求
- **技术点**:
  - 记录时间戳、操作类型、目标 URL、操作结果
  - 日志存储：本地文件或远程 syslog
  - 支持日志轮转和归档
  - 隐私保护：自动脱敏敏感数据

---

## P5 OpenCode 优化 (OpenCode Specific)

### 16. 触发词扩展
- **目标**: 扩展 SKILL.md 中的触发词，提高 Agent 识别准确率
- **当前触发词**: `browser`, `chrome`, `web`, `navigate`, `click`, `screenshot`
- **建议新增**: 
  - `scrape`, `crawl`, `extract`, `grab` (数据抓取场景)
  - `debug`, `inspect`, `devtools` (调试场景)
  - `automation`, `bot`, `robot` (自动化场景)
  - `headless`, `puppeteer`, `playwright` (同类工具联想)

### 17. Skill 版本标识
- **目标**: 在 SKILL.md 中明确标识版本号，便于 Agent 管理和用户追踪
- **实施方案**:
  - 在 SKILL.md 顶部添加 `version: 0.1.0`
  - 遵循语义化版本规范 (MAJOR.MINOR.PATCH)
  - 在 CLI 中增加 `--version` 参数
  - 在 PI_AGENT_SETUP.md 中说明版本兼容性

---

## 实施建议

### 短期 (1-2 周)
- [ ] 完成 P1 第 4-7 项
- [ ] 完成 P2 第 8-10 项
- [ ] 添加类型注解并通过 mypy 检查

### 中期 (1 个月)
- [ ] 完成 P3 第 11-13 项
- [ ] 完成 P4 第 14-15 项

### 长期 (持续优化)
- [ ] 完成 P5 第 16-17 项
- [ ] 根据用户反馈调整优先级

---

## 贡献指南

欢迎提交 PR 实现上述功能！提交前请确保：
1. 代码通过 `mypy` 类型检查
2. 新增功能有对应的 CLI 命令和文档更新
3. 遵循现有代码风格和项目结构
4. 在 SKILL.md 中更新功能说明

---

*最后更新: 2025-01-XX*
*版本: v0.1.0*
