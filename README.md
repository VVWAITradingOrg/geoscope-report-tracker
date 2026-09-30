# geoscope-report-tracker

Mac mini 上由 LaunchAgent 定时轮询触发、Codex CLI `gpt-6-sol` 做结构化摘要的 GeoScope 研报追踪。跟踪 `ljianhui90@gmail.com` 里来自 `updates@mail.geoscopeapp.com` 的研报推送邮件，为每篇文章生成核心观点/标的多空摘要，投递到对应 Discord 频道。OpenClaw 不参与分析，只作为 Discord 传输层。

## Run

```bash
./pipeline.sh --no-deliver   # 抓取+摘要+校验+渲染，不发送
./pipeline.sh                # 正式运行并发送
```

正式入口是 `pipeline.sh`。产物在 `output/<run_id>/`（含每篇文章的 prompt、Codex 原始输出、渲染后的 Discord 文本），日志在 `logs/`；均不进入 Git。

## 流程

1. `scripts/fetch.py`：用 `gog` 搜索来自 `updates@mail.geoscopeapp.com` 且未打 `geoscope-processed` label 的邮件，解析正文 metadata，下载 PDF 附件，按 `<来源>__<文章slug>` 分组累积到 `state/pending/<key>.json`，处理完的邮件打上 label（Gmail 侧去重，重跑不会重复下载）
2. `scripts/analyze.py`：对每个距首次出现已超过 `MERGE_WINDOW_MINUTES`（默认 15 分钟，等一等可能稍后才到的中文/双语版本）且还没投递过的 key，按 中文 > 双语 > 英文 优先级挑一份 PDF，用 PyMuPDF 抽取正文，套 `prompts/summarize.md` 模板调用 Codex CLI 生成结构化摘要 JSON
3. `scripts/validate.py`：语义校验（核心观点 3-5 条、标的 stance 枚举合法等），任何一条不过整个 run 失败，不投递
4. `scripts/render.py`：渲染成 Discord 文本，按 `config/sources.json` 里的来源→频道映射打包
5. `scripts/deliver.py`：`openclaw message send` 逐条发送成功后，写 `state/delivered/<key>.json` 标记，防止重复投递

## Credentials and delivery

- Gmail 读取：复用 `gog` CLI 已授权的 `ljianhui90@gmail.com`（scope 含 gmail），项目不新存任何凭据
- 分析：Codex CLI `gpt-6-sol`，复用本机 `ljianhui100@gmail.com` 的 ChatGPT 登录状态，项目不存 API key
- Discord：调用 `openclaw message send --account default`，凭据由 OpenClaw 现有配置管理；项目不读取或保存 bot token
- 目标频道：见 `config/sources.json`（只存频道 ID，不是密钥）；新增来源在这里加一行映射即可

## Scheduling and watchdog

- LaunchAgent：`com.vvw.geoscope-report-tracker`，每 5 分钟轮询一次（`StartInterval=300`），`RunAtLoad=true`
- 统一 watchdog：`/Users/vvw/Automation/manager/supervisor.py`（需要注册进 `manager/registry.json` 才会被巡检）
- heartbeat：`~/.openclaw/task-status/geoscope-report-tracker.json`

## 去重/幂等

两层：Gmail label `geoscope-processed` 防止重复下载同一封邮件；`state/delivered/<source>__<slug>.json` 防止同一篇文章（可能来自多封不同语言版本的邮件）被投递超过一次。都是文件/label 落地后才算数——`deliver.py` 只在真正发送成功后才写 delivered 标记。

## 部署前还没做的事

- [ ] `--no-deliver` 跑通几次，人工检查 `output/latest/discord/*/01.txt` 的摘要质量
- [ ] 注册进 `/Users/vvw/Automation/manager/registry.json`
- [ ] 拿到用户授权后，做一次真实投递（去掉 `--no-deliver`）确认 Discord 效果
- [ ] 拿到用户授权后，把 `launchd/com.vvw.geoscope-report-tracker.plist` 装到 `~/Library/LaunchAgents/` 并 `launchctl load`
