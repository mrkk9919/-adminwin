# Wing Bank 项目代码分类结构

## 一、前端（新版本 React App）

**项目路径**: `/Volumes/CODE/wiwinwiwing-1/wing-bank-latest/APP/`

**技术栈**: React 18 + Vite + TypeScript + Capacitor + wouter 路由

### 目录结构
```
APP/
├── src/
│   ├── App.tsx              # 主应用入口
│   ├── main.tsx             # React 挂载点
│   ├── index.css            # 全局样式
│   ├── components/          # 通用组件
│   ├── context/             # 全局状态（AccountContext, TransactionContext）
│   ├── pages/               # 页面组件（Register, Login, Home, PIN, KYC等）
│   ├── hooks/               # 自定义 Hooks
│   ├── i18n/                # 多语言（中/英/高棉语）
│   ├── data/                # 静态数据
│   └── lib/                 # 工具库
├── vite.config.ts           # Vite 配置（base: '/app/'）
├── package.json
└── tsconfig.json
```

### 关键文件
- `src/context/AccountContext.tsx` — 账户状态管理，每10秒轮询余额
- `src/context/TransactionContext.tsx` — 交易记录管理，每10秒轮询
- `src/pages/Register.tsx` — 注册+KYC流程
- `src/i18n/translations.ts` — 多语言翻译

### 构建部署
```bash
cd APP && npx vite build
# 产物: APP/dist/
# 部署到: /var/www/wingdigi.store/app/
```

---

## 二、后台（Admin 管理后台）

**项目路径**: `/Volumes/CODE/telegram bot/admin/`

**技术栈**: Python FastAPI + Jinja2 模板 + SQLite

### 目录结构
```
admin/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── auth.py              # JWT 认证
│   ├── config.py            # 配置管理
│   ├── database.py          # 数据库连接
│   ├── routers/             # 路由模块
│   │   ├── dashboard.py     # 仪表盘
│   │   ├── customers.py     # ⭐ 客户管理（刚改造）
│   │   ├── accounts.py      # 账户管理
│   │   ├── transactions.py  # 交易管理
│   │   ├── kyc.py           # KYC 审核
│   │   ├── messages.py      # 消息管理
│   │   ├── orders.py        # 订单管理
│   │   ├── groups.py        # 群组管理
│   │   ├── bots.py          # 机器人管理
│   │   ├── bridge.py        # 前端桥接 API
│   │   ├── client_bridge.py # 客户端桥接
│   │   ├── client_api.py    # 客户端 API
│   │   ├── sms.py           # SMS OTP
│   │   ├── push.py          # 推送通知
│   │   ├── reports.py       # 报表
│   │   └── settings.py      # 设置
│   ├── services/            # 业务服务
│   │   ├── telegram.py      # Telegram 消息发送
│   │   ├── khqr.py          # KHQR 支付
│   │   ├── fcm.py           # Firebase 推送
│   │   └── sms.py           # SMS 服务
│   ├── models/              # 数据模型
│   └── templates/           # Jinja2 模板
│       ├── base.html        # 基础布局
│       ├── login.html       # 登录页
│       ├── dashboard.html   # 仪表盘
│       ├── customers/       # ⭐ 客户模板（刚改造）
│       │   ├── list.html    # 客户列表
│       │   ├── detail.html  # 客户详情
│       │   ├── logs.html    # 操作日志（新增）
│       │   └── same_name.html # 同名查询（新增）
│       ├── accounts/        # 账户模板
│       ├── transactions/    # 交易模板
│       ├── kyc/             # KYC 模板
│       ├── messages/        # 消息模板
│       ├── orders/          # 订单模板
│       ├── groups/          # 群组模板
│       ├── bots/            # 机器人模板
│       ├── bridge/          # 桥接控制
│       ├── sms/             # SMS 管理
│       ├── push/            # 推送管理
│       ├── reports/         # 报表
│       └── settings/        # 设置
├── static/                  # 静态资源（CSS, JS, 图片）
├── requirements.txt         # Python 依赖
├── venv/                    # 虚拟环境
└── .env                     # 环境变量
```

### 关键配置
- 监听: `127.0.0.1:8080`
- 管理员: `admin / admin123`
- 数据库: `/opt/wingbank/shared.db`
- 依赖版本: **fastapi==0.104.1 + starlette==0.27.0**（必须）

### 部署路径
- 服务器: `/opt/wingbank/admin/`
- systemd: `admin.service`

---

## 三、机器人（Telegram Bot - Go）

**项目路径**: `/Volumes/CODE/telegram bot/tgbot/`

**技术栈**: Go + telebot.v3 + modernc.org/sqlite（CGO-free）

### 目录结构
```
tgbot/
├── main.go                  # 主入口
├── go.mod / go.sum          # 依赖管理
├── config/                  # 配置
├── db/                      # 数据库操作
│   ├── db.go                # 数据库连接
│   ├── customers.go         # 客户操作
│   ├── accounts.go          # 账户操作
│   ├── messages.go          # 消息操作
│   ├── orders.go            # 订单操作
│   ├── pending.go           # 待处理注册
│   └── heartbeat.go         # 心跳
├── handlers/                # 消息处理器
│   ├── commands.go          # 命令处理（/start, /help等）
│   ├── menu.go              # 菜单交互
│   ├── conversation.go      # 对话流程
│   ├── payment.go           # 支付处理
│   ├── khqr.go              # KHQR 扫码
│   ├── notify.go            # 通知发送
│   └── admin_notify.go      # 管理员通知
├── services/                # 外部服务
│   ├── httpclient.go        # HTTP 客户端
│   └── push.go              # 推送服务
├── middleware/              # 中间件
├── migrations/              # 数据库迁移
│   ├── 001_admin_tables.sql
│   ├── 002_banking_tables.sql
│   ├── 003_add_push_tokens.sql
│   ├── 004_add_bot_name.sql
│   ├── 005_add_external_to.sql
│   ├── 006_create_bots_table.sql
│   ├── 007_create_notification_groups.sql
│   └── 008_create_pending_registrations.sql
├── chatapi/                 # Chat API
└── tgbot                    # 编译产物
```

### 双 Bot 架构
- **主 Bot**: @wingbankkh_bot
- **副 Bot**: @PaywayABAbot（ABA Bank）

### 构建部署
```bash
cd tgbot && go build -o tgbot main.go
# 部署到: /opt/wingbank/bin/tgbot
# systemd: tgbot.service
```

---

## 四、管理机器人（TGAdmin - React 管理面板）

**项目路径**: `/Volumes/CODE/telegram bot/tgadmin/`

**技术栈**: Python FastAPI 后端 + React/TypeScript 前端

### 目录结构
```
tgadmin/
├── app/                     # Python 后端
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置
│   ├── database.py          # 数据库
│   ├── routers/             # API 路由
│   ├── schemas/             # Pydantic 模型
│   ├── models/              # 数据模型
│   ├── services/            # 业务服务
│   ├── static/              # 静态文件
│   └── templates/           # 模板
├── frontend/                # React 前端
│   ├── src/                 # 源码
│   ├── public/              # 公共资源
│   ├── dist/                # 构建产物
│   ├── vite.config.ts       # Vite 配置
│   ├── package.json
│   └── wrangler.toml        # Cloudflare Pages 配置
├── requirements.txt         # Python 依赖
├── venv/                    # 虚拟环境
└── .env                     # 环境变量
```

### 部署
- 后端: `/opt/wingbank/tgadmin/`，监听 `127.0.0.1:8002`
- 前端: `/var/www/wingdigi.store/tgbot/`
- systemd: `tgadmin.service`

---

## 五、API（新版本 Express 后端）

**项目路径**: `/Volumes/CODE/wiwinwiwing-1/wing-bank-latest/api-server/`

**技术栈**: Node.js Express + TypeScript + Drizzle ORM

### 目录结构
```
api-server/
├── src/                     # 源码
├── dist/                    # 编译产物
│   ├── index.mjs            # ⭐ 主入口（已多次修改）
│   ├── index.mjs.bak~.bak5  # 备份文件
│   └── thread-stream-worker.mjs
├── package.json
├── tsconfig.json
└── .env                     # 环境变量
```

### 自定义路由（已添加）
1. `GET /api/accounts/balance?phone=xxx` — 余额查询
2. `GET /api/accounts/transactions?phone=xxx` — 交易记录查询
3. KYC confirm 同步客户和账号到 shared.db

### 部署
- 服务器: `/opt/wingbank/api-server/`
- 监听: `0.0.0.0:5001`
- systemd: `wingbank-api.service`

---

## 六、数据库（SQLite）

**文件路径**: 
- 本地: `/Volumes/CODE/telegram bot/shared.db`
- 服务器: `/opt/wingbank/shared.db`

### 主要表结构
```
customers              # 客户表（telegram_id PK, username, phone, role, is_active...）
accounts               # 账户表（account_number, currency, balance...）
transactions           # 交易表（type: transfer/deposit/withdrawal/exchange）
kyc_records            # KYC 记录表（含照片字段: selfie_photo, id_front_photo, id_back_photo）
account_logs           # ⭐ 操作日志表（新增）
messages               # 消息表
orders                 # 订单表
groups                 # 群组表
bots                   # 机器人表
pending_registrations  # 待处理注册
notification_groups    # 通知群组
```

### 关键约定
- USD 余额以**分**为单位存储（cents），显示时除以 100
- KHR 余额直接存储整数
- phone 格式：数据库存 `979935566`，前端存 `+855 979935566`

---

## 七、部署配置

### Nginx
- 配置: `/etc/nginx/conf.d/wingdigi.store.conf`
- 前端静态: `/var/www/wingdigi.store/app/`
- `/api/` → api-server (5001)
- `/app/api/` → admin (8080)

### systemd 服务
| 服务 | 端口 | 路径 |
|------|------|------|
| wingbank-api | 5001 | /opt/wingbank/api-server/ |
| admin | 8080 | /opt/wingbank/admin/ |
| tgadmin | 8002 | /opt/wingbank/tgadmin/ |
| tgbot | - | /opt/wingbank/bin/tgbot |
| nginx | 80,443 | - |

### TLS
- Let's Encrypt: `/etc/letsencrypt/live/wingdigi.store/`
