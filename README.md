# 🤖 AI Recruiter Bot

> 全自动候选人搜索、邮件触达、回复处理与面试预约系统

基于 Claude AI 驱动的招聘自动化工具。输入目标公司和岗位，机器人自动完成从候选人发现到面试预约的完整流程。

---

## 功能概览

| 模块 | 功能 |
|------|------|
| 🔍 **候选人搜索** | 通过 Google / Google Scholar 搜索目标公司人才 |
| 📧 **邮箱发现** | Hunter.io API + 规则推断，自动找到候选人邮箱 |
| ✍️ **个性化外发** | Claude 根据候选人背景生成定制化 outreach 邮件 |
| 📬 **回复监听** | Gmail API 实时监听收件箱 |
| 🧠 **意图分类** | Claude Haiku 自动识别回复类型（感兴趣/拒绝/提问/安排时间） |
| ↩️ **自动回复** | Claude Opus 根据意图生成个性化回复 |
| 📅 **面试预约** | 自动在邮件中发送 Calendly 链接，候选人自助预约 |
| 🔁 **跟进提醒** | 5 天无回复自动发送 follow-up |
| 📊 **实时看板** | 终端实时显示 pipeline 状态与活动日志 |

---

## 架构

```
recruiter-bot/
├── main.py          # CLI 入口（所有命令）
├── watcher.py       # 自动驾驶守护进程 + 实时面板
├── searcher.py      # Google / Google Scholar 候选人搜索
├── email_finder.py  # Hunter.io 邮箱发现 + 规则兜底
├── outreach.py      # Claude 生成外发邮件 & 回复
├── classifier.py    # Claude Haiku 回复意图分类
├── gmail_client.py  # Gmail API 收发邮件
├── db.py            # SQLite 候选人全生命周期管理
├── config.py        # 环境变量读取
└── .env.example     # 配置模板
```

---

## 快速开始

### 1. 安装依赖

```bash
git clone https://github.com/Zuiaiaertai/recruiter-bot.git
cd recruiter-bot
pip install -r requirements.txt
```

### 2. 配置 API Keys

```bash
cp .env.example .env
```

编辑 `.env` 填入以下内容：

```env
# Claude AI
ANTHROPIC_API_KEY=sk-ant-...

# Google 搜索（serper.dev，$1/1000 次）
SERPER_API_KEY=...

# 邮箱发现（hunter.io，25 次/月免费）
HUNTER_API_KEY=...

# 发件人信息
SENDER_EMAIL=you@gmail.com
RECRUITER_NAME=Your Name
RECRUITER_TITLE=Talent Partner
RECRUITER_COMPANY=Your Company

# Calendly 预约链接
CALENDLY_EVENT_URL=https://calendly.com/yourname/30min
```

### 3. 配置 Gmail OAuth（一次性）

1. 前往 [Google Cloud Console](https://console.cloud.google.com)
2. 新建项目 → 启用 **Gmail API**
3. 创建 OAuth 2.0 凭据（桌面应用类型）
4. 下载 `credentials.json`，放到 `credentials/credentials.json`
5. 首次运行时浏览器会弹出授权页面，点击同意即可

---

## 使用方式

### 完整一键流程

```bash
# 先 dry-run 预览邮件内容
python main.py run \
  --company "OpenAI" \
  --role "ML Engineer" \
  --job job.txt \
  --limit 15 \
  --dry-run

# 确认无误后正式发送
python main.py run -c "OpenAI" -r "ML Engineer" -j job.txt -n 15
```

### 分步执行

```bash
# 第一步：搜索候选人
python main.py search -c "Anthropic" -r "Researcher" -n 20

# 第二步：发现邮箱
python main.py find-emails -c "Anthropic"

# 第三步：发送外发邮件（先 dry-run 确认）
python main.py send-outreach -c "Anthropic" -j job.txt --dry-run
python main.py send-outreach -c "Anthropic" -j job.txt

# 查看候选人状态
python main.py list
python main.py list --status interested
```

### 自动驾驶模式（推荐）

```bash
python main.py watch -j job.txt -i 15 -f 5
#                                  ↑       ↑
#                            每15分钟   5天无回复自动跟进
```

启动后终端实时显示：

```
🤖 AI Recruiter Bot  │  cycle #4  │  now 14:32:01  │  next check 14:47:01
┌─ Pipeline ──────────┐  ┌─ Recent Activity ──────────────────────────────┐
│ discovered      12  │  │ Jane Smith    OpenAI      interested  14:28   │
│ emailed          8  │  │ Bob Chen      Anthropic   emailed     13:45   │
│ replied          3  │  │ Wei Liu       DeepMind    replied     12:10   │
│ interested       2  │  └────────────────────────────────────────────────┘
│ not_interested   1  │
│ TOTAL           26  │   Activity Log:
└─────────────────────┘   14:32:01  ✉️  Processed 2 replies
                          14:32:03  ↩️  Sent 1 follow-up (>5d silent)
```

---

## 候选人状态流转

```
discovered
    │
    ▼ find-emails
  (email added)
    │
    ▼ send-outreach
  emailed
    │
    ├──► [5天无回复] ──► follow-up 自动发送
    │
    ▼ 候选人回复
  replied
    │
    ├──► interested ──► 自动回复 + 发 Calendly 链接
    ├──► not_interested
    └──► question ──► 自动回答问题
```

---

## 所需 API 及费用

| 服务 | 用途 | 费用 |
|------|------|------|
| [Anthropic](https://console.anthropic.com) | 邮件生成 + 回复分类 | 按 token 计费 |
| [Serper](https://serper.dev) | Google 搜索 | $1 / 1000 次 |
| [Hunter.io](https://hunter.io) | 邮箱发现 | 25 次/月免费 |
| Gmail API | 收发邮件 | 免费 |
| [Calendly](https://calendly.com) | 面试预约 | 免费套餐可用 |

---

## 注意事项

- 发送外发邮件前务必使用 `--dry-run` 预览
- Hunter.io 免费额度用完后可切换为规则推断模式（自动兜底）
- Gmail OAuth token 存储在 `credentials/token.json`，请勿提交到 Git
- 建议每批次发送不超过 50 封，避免 Gmail 触发频率限制
