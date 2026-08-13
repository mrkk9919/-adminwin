# Wing Bank Telegram Bot 系统 — 项目总结

**域名**: https://wingdigi.store
**服务器**: 159.198.39.205 (CentOS Stream 9, 2 vCPU / 3.6GB RAM / 60GB SSD)
**部署日期**: 2026-08-09
**最后更新**: 2026-08-10

---

## 一、Wing Bank 前端

**地址**: https://wingdigi.store/app/
**技术栈**: React 18 + TypeScript + Vite + Capacitor（移动端封装）
**界面语言**: 高棉语（km-KH），支持中/英切换
**服务器路径**: `/var/www/wingdigi.store/app/`

### 功能页面

| 页面 | 路由 | 说明 |
|------|------|------|
| 登录/注册 | `/` | 手机号+密码登录，新用户自动注册，支持 `?forceRegister=1` 直接注册 |
| PIN 码 | `/pin` | 4位交易 PIN 验证 |
| 我的账户 | `/my-account` | 账户余额、账户信息 |
| 充值 | `/topup` | 手机话费充值 |
| 扫码支付 | `/scan` | QR 扫码（含 qr-scanner-worker） |
| QR 支付 | `/qr-payment` | 出示付款码 |
| 我的 QR | `/my-qr` | 收款二维码 |
| 转账 | `/transfer` | 转账首页 |
| 同名转账 | `/transfer/self` | 自己名下账户互转 |
| Wing 内转 | `/transfer/wing` | Wing 账户间转账 |
| 他行转账 | `/transfer/other-bank` | 转账到其他银行 |
| Wing Luy | `/transfer/weiluy` | Wing Luy 国际汇款 |
| 商户 | `/merchant` | Wing 代理商验证（8位代码） |
| 贷款 | `/loan` | 贷款服务 |
| 银行卡 | `/bank-card` | 银行卡管理 |
| 通知 | `/notifications` | 交易通知推送 |
| 交易记录 | `/account/:id/transactions` | 账户交易历史 |
| 交易详情 | `/transaction/:txId` | 单笔交易详情 |
| 交易凭证 | `/transaction-receipt/:txId` | 电子凭证 |
| 个人资料 | `/more/profile` | 用户资料编辑 |
| 设置 | `/more/settings` | 应用设置 |
| 语言 | `/more/language` | 语言切换 |
| 联系我们 | `/more/contact` | 客服信息 |
| 关于 | `/more/about` | Wing Bank 介绍 |
| 常见问题 | `/more/faq` | FAQ |
| 条款 | `/more/terms` | 服务条款 |
| 推荐 | `/more/refer` | 推荐好友（$5奖励） |
| 网点 | `/more/branches` | 分行/ATM/代理商地图 |
| 利息计算 | `/more/interest-calculator` | 利息计算器 |
| 帮助 | `/help` | 帮助中心 |

### 前端 API

- **API 基础路径**: `/app/api`（nginx 代理至 `127.0.0.1:8001`）
- **注册**: `POST /app/api/client/auth/register` — 手机号、密码、姓名
- **登录**: `POST /app/api/client/auth/login` — 返回 JWT Token
- **账户**: `GET /app/api/client/accounts` — 查询 USD/KHR 余额
- **转账**: `POST /app/api/client/transfer` — 同行/跨行转账
- **交易记录**: `GET /app/api/client/transactions` — 分页查询
- **KYC**: `POST /app/api/kyc/confirm` — 实名认证
- **Bridge 轮询**: `GET /app/api/client/bridge/poll` — 每5秒轮询管理端指令

### 支持银行（25家）

Wing Bank、ABA Bank、ACLEDA、Canadia、Bakong (NBC)、Chip Mong、Phillip Bank、J Trust Royal、Sathapana、Maybank、Vattanac、FTB、Hattha、Campu、Prince Bank、BRED、CIMB、RHB、KB Kookmin、Shinhan、Amret、LOLC、AMK、Post Bank、UCB、Pi Pay

### PWA 支持

- Service Worker (`/sw.js`) 支持离线缓存和推送通知
- Web App Manifest，可添加到手机主屏幕
- Capacitor 封装，可打包为 Android/iOS 原生应用

---

## 二、Wing Bank 管理后台

**地址**: https://wingdigi.store/admin/
**登录**: admin / admin123
**技术栈**: FastAPI + Jinja2 服务端渲染 + Bootstrap 5
**服务器路径**: `/opt/wingbank/admin/`
**端口**: 127.0.0.1:8001（nginx 反向代理）

### 后台功能模块

| 模块 | 路由 | 功能 |
|------|------|------|
| 仪表盘 | `/dashboard` | 数据统计概览（用户数、交易量、Bot状态） |
| 客户管理 | `/customers` | 客户列表、搜索、详情、编辑 |
| 客户详情 | `/customers/:id` | 资料编辑、余额调整、KYC审核、交易记录 |
| 账户管理 | `/accounts` | 银行账户列表、状态管理 |
| 交易记录 | `/transactions` | 所有交易查询、筛选 |
| 消息管理 | `/messages` | 向用户发送 Telegram 消息 |
| KYC 审核 | `/kyc` | 实名认证审核（通过/拒绝） |
| 订单管理 | `/orders` | 支付订单查看 |
| Bot 管理 | `/bots` | Bot 状态监控、心跳检测 |
| 推送通知 | `/push` | FCM 推送通知发送 |
| 短信管理 | `/sms` | SMS 发送记录 |
| 群发分组 | `/groups` | 通知分组管理 |
| Bridge 控制 | `/bridge` | App 远程指令控制台 |
| 报表 | `/reports` | 数据报表导出 |
| 系统设置 | `/settings` | 系统参数配置 |

### 客户管理增强功能

- **多字段搜索**: 手机号、Wing 账号、姓名、KYC 姓名、邮箱、Telegram ID
- **余额显示**: 列表直接显示 USD/KHR 余额和账号
- **余额调整**: 后台直接加钱/扣钱，自动生成交易记录
- **资料编辑**: 姓名、电话、邮箱、角色、状态、备注
- **KYC 管理**: 查看证件信息、审核通过/拒绝
- **交易历史**: 客户最近10条交易记录
- **发送通知**: 直接向客户推送 Telegram 消息

### App 控制面板

**地址**: https://wingdigi.store/admin/app/

独立的 App 远程控制界面，功能：
- **推送消息**: Info / Success / Warning / Error 四种类型
- **推送指令**: 刷新、页面跳转、弹窗、登出、清除缓存、自定义指令
- **余额更新**: 远程更新 App 显示的 USD/KHR 余额
- **权限控制**: 转账、扫码、充值、提现、锁屏
- **实时预览**: 左侧手机模拟器实时显示效果
- **命令历史**: 右侧记录所有已发送指令
- **设备轮询**: 每3秒检查在线设备

### Client API（前端 App 接口）

| 接口 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/api/client/auth/register` | POST | 无 | 用户注册，自动创建 USD/KHR 账户 |
| `/api/client/auth/login` | POST | 无 | 用户登录，返回 JWT |
| `/api/client/accounts` | GET | Bearer | 查询账户余额 |
| `/api/client/transfer` | POST | Bearer | 转账（事务性扣款+存款） |
| `/api/client/transactions` | GET | Bearer | 交易记录（分页） |
| `/api/client/bridge/poll` | GET | 无 | 轮询管理端指令 |
| `/api/client/bridge/ack` | POST | 无 | 确认指令 |
| `/api/client/bridge/register` | POST | 无 | 设备注册/心跳 |

### Client Bridge（远程指令系统）

- 公开接口，无需认证
- 支持广播指令和设备专属指令
- 指令类型：update-balance、set-permissions、refresh、navigate、show-alert、logout、clear-cache
- 设备 ID 存储在 localStorage，格式 `web-` + 随机字符串
- App 每5秒轮询一次

---

## 三、机器人管理（tgadmin）

**API 地址**: https://wingdigi.store/tgbot/api/
**前端地址**: https://wingdigi.store/tgbot/
**技术栈**: FastAPI 后端（端口 8002）+ React/TypeScript 前端（Vite + React Router + Bootstrap 5）
**服务器路径**: `/opt/wingbank/tgadmin/`

### 功能

- **仪表盘**: Bot 运行状态、消息统计
- **用户管理**: Telegram 用户列表和管理
- **Bot 管理**: 多 Bot 配置和监控
- **API 接口**: RESTful API 供前端调用
- **2 Workers**: 生产环境双进程运行

### 后端路由

| 模块 | 说明 |
|------|------|
| `api.py` | 通用 API |
| `bots_api.py` | Bot 管理 API |
| `users_api.py` | 用户管理 API |
| `users.py` | 用户页面 |
| `dashboard.py` | 仪表盘页面 |

---

## 四、机器人（ABA + Wing）+ 数据库

### Telegram 机器人

**技术栈**: Go 1.26 + telebot.v3 + modernc.org/sqlite（CGO-free，纯 Go SQLite）
**二进制**: `/opt/wingbank/bin/tgbot`（11MB，静态链接，Linux amd64）
**工作目录**: `/opt/wingbank/tgbot/`

#### Wing Bank 主 Bot

- **用户名**: @wingbankkh_bot
- **Bot ID**: 8845776726
- **模式**: 完整功能模式
- **功能**: 用户交互、转账通知、收款提醒、KYC 流程

#### ABA Bank 副 Bot

- **用户名**: @PaywayABAbot
- **Bot ID**: 8682768706
- **模式**: chat-only 轻量模式
- **功能**: ABA 银行转账凭证推送、聊天中继

#### Bot 特性

- 双 Bot 并行运行，共享同一数据库
- 心跳检测（每30秒写入 `bot_heartbeats` 表）
- 自动数据库迁移（8个迁移文件，启动时自动执行）
- 长轮询（Long Polling），10秒超时
- 推送通知集成（FCM + APNs）
- 支付回调处理
- 转账凭证生成（ABA Bank 英文卡片样式）

### 数据库

**类型**: SQLite 3（WAL 模式）
**路径**: `/opt/wingbank/shared.db`
**大小**: 184KB（已清空，全新状态）
**完整性**: PRAGMA integrity_check = ok

#### 数据表结构

| 表名 | 说明 |
|------|------|
| `customers` | 客户信息（Telegram用户 + Web注册用户） |
| `accounts` | 银行账户（USD/KHR，9位账号） |
| `transactions` | 交易记录（转账/存款/取款/兑换） |
| `messages` | 消息记录 |
| `kyc_records` | KYC 实名认证记录 |
| `orders` | 支付订单 |
| `bots` | Bot 配置信息 |
| `bot_heartbeats` | Bot 心跳状态 |
| `pending_registrations` | 待确认注册 |
| `notification_groups` | 通知分组 |
| `sms_logs` | 短信发送记录 |
| `users` | 管理员用户 |

#### 客户表字段

```
telegram_id    INTEGER PRIMARY KEY  -- Telegram ID（Web用户从9000000001递增）
username       TEXT                 -- Telegram 用户名
first_name     TEXT                 -- 名
last_name      TEXT                 -- 姓
phone          TEXT                 -- 手机号
email          TEXT                 -- 邮箱
role           TEXT DEFAULT 'customer'  -- customer/vip/banned
is_active      INTEGER DEFAULT 1    -- 启用状态
web_registered INTEGER DEFAULT 0    -- 是否Web注册
password_hash  TEXT                 -- PBKDF2-SHA256 密码哈希
password_salt  TEXT                 -- 密码盐值
fcm_token      VARCHAR(255)         -- FCM 推送令牌
apns_token     VARCHAR(255)         -- APNs 推送令牌
notes          TEXT                 -- 管理员备注
created_at     DATETIME
updated_at     DATETIME
```

#### 账户表字段

```
id             INTEGER PRIMARY KEY AUTOINCREMENT
customer_id    INTEGER NOT NULL     -- 关联 customers.telegram_id
account_number TEXT UNIQUE          -- 9位账号（0开头）
currency       TEXT DEFAULT 'USD'   -- USD / KHR
balance        INTEGER DEFAULT 0    -- USD存分，KHR存整数
status         TEXT DEFAULT 'active' -- active/frozen/closed
type           TEXT DEFAULT 'wallet' -- wallet/savings/current
```

#### 交易表字段

```
id             INTEGER PRIMARY KEY
from_account_id INTEGER             -- 转出账户
to_account_id   INTEGER             -- 转入账户
amount          INTEGER             -- 金额
currency        TEXT                -- USD/KHR
type            TEXT                -- transfer/deposit/withdrawal/exchange
status          TEXT                -- completed/pending/failed/reversed
description     TEXT
reference_id    TEXT                -- 交易参考号（TXN+时间戳）
external_to     TEXT
created_at      DATETIME
```

#### 安全特性

- 密码加密: PBKDF2-SHA256，100,000 次迭代，16字节随机盐
- JWT 认证: HS256 签名，30天有效期
- 事务性转账: SQLite 事务保证扣款和存款原子性
- 账号生成: 9位数字，0开头，UNIQUE 约束

---

## 五、systemd + Nginx + TLS

### systemd 服务管理

全部服务配置为 `on-failure` 自动重启（5秒间隔），开机自启。

| 服务 | 说明 | 端口 | Workers |
|------|------|------|---------|
| `tgbot.service` | Go Telegram 机器人 | — | 1 |
| `admin.service` | FastAPI 管理后台 | 127.0.0.1:8001 | 1 |
| `tgadmin.service` | FastAPI 机器人管理 | 127.0.0.1:8002 | 2 |
| `nginx.service` | Nginx 反向代理 | 80, 443 | — |

**服务管理命令**:
```bash
systemctl start/stop/restart/status tgbot admin tgadmin nginx
journalctl -u tgbot -f          # 查看日志
systemctl enable tgbot          # 开机自启
```

### Nginx 反向代理

**配置文件**: `/etc/nginx/conf.d/wingdigi.store.conf`

#### 路由表

| 路径 | 后端 | 说明 |
|------|------|------|
| `/` | 静态文件 | 首页落地页 |
| `/receipt` | 静态文件 | ABA 转账凭证页 |
| `/bot/` | 静态文件 | 机器人介绍页 |
| `/app/` | 静态文件 | Wing Bank App（React SPA） |
| `/app/api/` | `127.0.0.1:8001/api/` | App 后端 API |
| `/admin/` | `127.0.0.1:8001/` | Wing Bank 管理后台 |
| `/admin/static/` | `127.0.0.1:8001/static/` | 后台静态资源 |
| `/admin/app/` | 静态文件 | App 控制面板 |
| `/admin/app/api/` | `127.0.0.1:8001/` | Client API |
| `/tgbot/` | 静态文件 | 机器人管理前端（React SPA） |
| `/tgbot/api/` | `127.0.0.1:8002/api/` | 机器人管理 API |
| `/health` | — | 健康检查（返回 OK） |

#### 特性

- HTTP 80 全部 301 跳转 HTTPS
- `sub_filter` 自动重写后台页面路径（`/` → `/admin/`）
- SPA 路由支持（try_files）
- 静态资源缓存
- gzip 压缩
- SELinux 兼容（httpd_sys_content_t）

### TLS/SSL 证书

- **签发机构**: Let's Encrypt
- **签发方式**: certbot --nginx（自动验证+配置）
- **证书路径**: `/etc/letsencrypt/live/wingdigi.store/`
- **有效期**: 2026-08-10 至 2026-11-08（90天）
- **自动续期**: certbot timer 已启用，自动续期
- **协议**: TLS 1.2 / 1.3
- **加密套件**: Mozilla 中间配置
- **评分**: A+（SSL Labs）

### 服务器安全

- SSH 端口: 22022（非默认）
- SELinux: Enforcing
- firewalld: 未运行（云防火墙安全组管控）
- 仅暴露 80/443/22022 端口
- 内部服务绑定 127.0.0.1，不对外暴露
- IP 白名单中间件（ALLOWED_IPS 为空时允许所有）

---

## 六、后台所有功能汇总

### 客户管理
- [x] 客户列表（分页）
- [x] 多字段搜索（手机号、账号、姓名、KYC、邮箱、Telegram ID）
- [x] 客户详情页
- [x] 编辑客户资料（姓名、电话、邮箱、角色、状态、备注）
- [x] 余额调整（加钱/扣钱，自动生成交易记录）
- [x] 账户查看（USD/KHR 账号、余额、状态）
- [x] 冻结/解冻账户
- [x] 角色管理（customer/vip/banned）
- [x] 发送 Telegram 通知

### 交易管理
- [x] 交易记录列表
- [x] 交易筛选（类型、状态、日期）
- [x] 交易详情
- [x] 交易参考号查询
- [x] 存款/取款记录（后台调整自动生成）

### KYC 实名认证
- [x] KYC 提交列表
- [x] 证件信息查看（姓名、证件号、出生日期、地址）
- [x] 审核通过
- [x] 审核拒绝（填写拒绝原因）
- [x] KYC 状态跟踪

### 消息与通知
- [x] 单发 Telegram 消息
- [x] 群发消息（按分组）
- [x] FCM 推送通知（Android）
- [x] APNs 推送（iOS）
- [x] 通知分组管理
- [x] SMS 短信发送（WINGSMS）
- [x] 消息发送记录

### Bot 管理
- [x] 双 Bot 状态监控（Wing + ABA）
- [x] 心跳检测（实时在线状态）
- [x] Bot 版本信息
- [x] 多 Bot Token 配置

### App 远程控制
- [x] 推送通知消息（4种类型）
- [x] 推送指令（刷新/跳转/弹窗/登出/清缓存）
- [x] 远程更新余额
- [x] 权限控制（转账/扫码/充值/提现/锁屏）
- [x] 设备在线状态
- [x] 命令历史记录
- [x] 手机模拟器实时预览

### 订单与支付
- [x] 订单列表
- [x] 支付回调处理
- [x] 支付确认接口

### 报表
- [x] 数据统计仪表盘
- [x] 客户增长统计
- [x] 交易量统计
- [x] 报表导出

### 系统
- [x] 管理员登录（JWT 认证）
- [x] 系统设置
- [x] 健康检查接口
- [x] 操作日志
- [x] 数据库迁移自动执行

### 前端 App 用户功能
- [x] 手机号注册/登录
- [x] JWT Token 认证
- [x] USD/KHR 双币种账户
- [x] 余额查询
- [x] Wing 内转账
- [x] 同名账户互转
- [x] 他行转账
- [x] 交易记录
- [x] 交易凭证
- [x] QR 扫码支付
- [x] 收款二维码
- [x] 手机充值
- [x] KYC 实名认证
- [x] 推送通知
- [x] 远程指令响应
- [x] 多语言（高棉语/中文/英文）
- [x] PWA 离线支持

---

## 七、部署架构图

```
                          Internet
                             |
                        [Cloud Firewall]
                             |
                    +--------+--------+
                    |   Nginx :443    |
                    |   (TLS Term.)   |
                    +--------+--------+
                             |
          +------------------+------------------+
          |                  |                  |
   /app/ (static)    /admin/ (proxy)    /tgbot/ (static)
   /app/api/  -----> |                  | /tgbot/api/ --> [tgadmin:8002]
                     v                  v
              +-------------+    +-------------+
              | admin:8001  |    | tgadmin:8002|
              |  (FastAPI)  |    |  (FastAPI)  |
              |  1 worker   |    |  2 workers  |
              +------+------+    +-------------+
                     |
                     v
              +-------------+
              |  shared.db  |
              |   (SQLite)  |
              +------+------+
                     |
                     v
              +-------------+
              |  tgbot      |
              |  (Go)       |
              |  Wing + ABA |
              +------+------+
                     |
                     v
              Telegram API
             (Long Polling)
```

### 目录结构

```
/opt/wingbank/
├── bin/tgbot              # Go 二进制（11MB，静态链接）
├── tgbot/
│   ├── .env               # Bot 配置
│   └── migrations/        # 8个 SQL 迁移文件
├── admin/
│   ├── app/
│   │   ├── main.py        # FastAPI 入口
│   │   ├── auth.py        # JWT 认证
│   │   ├── config.py      # 配置
│   │   ├── database.py    # SQLite 工具
│   │   ├── routers/       # 18个路由模块
│   │   ├── templates/     # Jinja2 模板
│   │   ├── static/        # CSS/JS/图片
│   │   └── services/      # Telegram/FCM 服务
│   ├── venv/              # Python 虚拟环境
│   └── .env
├── tgadmin/
│   ├── app/               # FastAPI 后端
│   ├── venv/
│   └── .env
└── shared.db              # SQLite 共享数据库

/var/www/wingdigi.store/
├── index.html             # 首页落地页
├── receipt.html           # ABA 转账凭证页
├── bot/                   # 机器人介绍页
├── app/                   # Wing Bank App（React SPA）
├── admin/app/             # App 控制面板
└── tgbot/                 # 机器人管理前端（React SPA）

/etc/nginx/conf.d/wingdigi.store.conf
/etc/letsencrypt/live/wingdigi.store/
/etc/systemd/system/{tgbot,admin,tgadmin}.service
```

---

## 八、技术栈汇总

| 组件 | 技术 | 版本 |
|------|------|------|
| 机器人 | Go + telebot.v3 | Go 1.26 |
| 管理后台 | Python + FastAPI + Jinja2 | Python 3.9 |
| 机器人管理 | FastAPI + React + TypeScript | React 18 |
| Wing App | React + TypeScript + Vite + Capacitor | React 18 |
| 数据库 | SQLite (WAL模式) | 3 |
| Web服务器 | Nginx | 1.20.1 |
| TLS证书 | Let's Encrypt (certbot) | 自动续期 |
| 进程管理 | systemd | — |
| 操作系统 | CentOS Stream 9 | 内核 5.14 |
| 密码加密 | PBKDF2-SHA256 | 100k iterations |
| API认证 | JWT (HS256) | 30天有效期 |
| 推送通知 | FCM + APNs | — |
| 版本控制 | Git | 2.52 |

---

*文档生成时间: 2026-08-10 23:10 UTC+7*
