# Wing Bank - 1Panel 部署指南

> **服务器**: 104.207.92.119  
> **面板地址**: http://104.207.92.119:2022/f148b3b1f8  
> **部署内容**: 1. 管理后台 2. Telegram 机器人

---

## 📋 目录

1. [前置准备](#前置准备)
2. [方式一：1Panel 面板部署（推荐）](#方式一1panel-面板部署推荐)
3. [方式二：SSH 命令行部署](#方式二ssh-命令行部署)
4. [配置说明](#配置说明)
5. [服务管理](#服务管理)
6. [常见问题](#常见问题)

---

## 🔧 前置准备

### 1. 登录 1Panel 面板

访问：http://104.207.92.119:2022/f148b3b1f8

- 用户名：`Admin`
- 密码：`f24ea46b56`

### 2. 安装必要环境

在 1Panel 面板中安装：
- **Python 3.9+**（用于管理后台）
- **Go 1.22+**（用于编译机器人，可选，也可以本地编译好上传）
- **Nginx**（用于反向代理）

### 3. 准备代码

将整个项目打包上传到服务器：
```bash
# 在本地电脑上打包
cd "/Volumes/CODE/telegram bot"
zip -r wingbank-bot.zip . -x "*.git*" "*/venv/*" "*/node_modules/*" "*.DS_Store"
```

然后通过 1Panel 的文件管理器上传到 `/opt/wingbank-bot/` 目录。

---

## 🖥️ 方式一：1Panel 面板部署（推荐）

### 第一部分：部署管理后台（Admin）

#### 步骤 1：创建 Python 项目

1. 进入 1Panel 面板 → **网站** → **Python 项目**
2. 点击 **创建项目**
3. 填写信息：
   - **项目名称**：`wingbank-admin`
   - **运行环境**：Python 3.9+
   - **项目目录**：`/opt/wingbank-bot/admin`
   - **启动方式**：uvicorn
   - **启动文件**：`app.main:app`
   - **端口**：`8000`
   - **域名**：（暂时留空，用 IP 访问）

#### 步骤 2：配置环境变量

在项目设置中，添加环境变量：

```env
# Bot 配置
BOT_TOKEN=8682768706:AAGFDk_dsW_-HTwNUijPMR66rjumeQFupZg

# 数据库
DATABASE_PATH=/opt/wingbank-bot/shared.db

# 管理员登录
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
JWT_SECRET=请改成随机字符串

# 服务器配置
HOST=0.0.0.0
PORT=8000

# IP 白名单（空 = 允许所有）
ALLOWED_IPS=

# FCM 推送（可选）
FCM_SERVER_KEY=

# 支付回调 Token
PAYMENT_API_TOKEN=6da90fc90e0b5468554082c8d364300f1224db89abdece7b

# 管理员 Telegram ID
ADMIN_TELEGRAM_ID=8619129145
```

#### 步骤 3：安装依赖

在项目的虚拟环境中安装依赖：
```bash
cd /opt/wingbank-bot/admin
pip install -r requirements.txt
```

#### 步骤 4：启动项目

点击启动按钮，等待项目启动成功。

#### 步骤 5：配置 Nginx 反向代理（可选）

如果需要用域名或 80 端口访问：

1. 进入 **网站** → **网站** → **创建网站**
2. 填写域名（或用 IP）
3. 在网站设置中，配置反向代理：
   - 代理地址：`http://127.0.0.1:8000`

---

### 第二部分：部署 Telegram 机器人（TGBot）

#### 方式 A：本地编译后上传（推荐，服务器不需要 Go 环境）

##### 步骤 1：本地编译 Go 程序

```bash
cd "/Volumes/CODE/telegram bot/tgbot"

# Linux AMD64 编译
GOOS=linux GOARCH=amd64 go build -o tgbot-linux-amd64 main.go
```

编译完成后，会生成 `tgbot-linux-amd64` 文件。

##### 步骤 2：上传到服务器

通过 1Panel 文件管理器，把 `tgbot-linux-amd64` 上传到 `/opt/wingbank-bot/tgbot/` 目录。

##### 步骤 3：添加进程守护

1. 进入 1Panel 面板 → **进程守护**
2. 点击 **创建守护进程**
3. 填写信息：
   - **名称**：`wingbank-tgbot`
   - **运行用户**：`root`
   - **启动命令**：`/opt/wingbank-bot/tgbot/tgbot-linux-amd64`
   - **运行目录**：`/opt/wingbank-bot/tgbot`
   - **环境变量**：
     ```
     BOT_TOKEN=8682768706:AAGFDk_dsW_-HTwNUijPMR66rjumeQFupZg
     DATABASE_PATH=/opt/wingbank-bot/shared.db
     PUSH_BASE_URL=http://localhost:8000
     ```

#### 方式 B：服务器上编译（需要安装 Go）

如果服务器上已经安装了 Go 环境：

1. 进入 `/opt/wingbank-bot/tgbot` 目录
2. 执行 `go build -o tgbot main.go`
3. 然后用进程守护启动

---

## 🚀 方式二：SSH 命令行部署

如果你有 SSH 权限，可以用一键部署脚本。

### 步骤 1：连接服务器

```bash
ssh root@104.207.92.119
```

### 步骤 2：上传代码

```bash
# 在本地电脑上执行
scp wingbank-bot.zip root@104.207.92.119:/opt/
```

### 步骤 3：解压代码

```bash
cd /opt
unzip wingbank-bot.zip -d wingbank-bot
cd wingbank-bot
```

### 步骤 4：运行一键部署脚本

```bash
bash deploy/deploy-1panel.sh
```

脚本会自动完成：
- 安装系统依赖
- 配置 Python 虚拟环境
- 编译 Go 程序
- 配置 systemd 服务
- 启动所有服务

---

## ⚙️ 配置说明

### 管理后台配置（admin/.env）

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `BOT_TOKEN` | Telegram Bot Token | 必填 |
| `DATABASE_PATH` | SQLite 数据库路径 | `../shared.db` |
| `ADMIN_USERNAME` | 管理员用户名 | `admin` |
| `ADMIN_PASSWORD` | 管理员密码 | `admin123` |
| `JWT_SECRET` | JWT 密钥 | 请修改 |
| `HOST` | 监听地址 | `127.0.0.1` |
| `PORT` | 监听端口 | `8080` |
| `ALLOWED_IPS` | IP 白名单 | 空（允许所有） |
| `FCM_SERVER_KEY` | FCM 推送密钥 | 可选 |
| `PAYMENT_API_TOKEN` | 支付回调 Token | 可选 |

### 机器人配置（tgbot）

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `BOT_TOKEN` | Telegram Bot Token | 必填 |
| `DATABASE_PATH` | SQLite 数据库路径 | `./shared.db` |
| `PUSH_BASE_URL` | 推送服务地址 | `http://localhost:8000` |

---

## 🔧 服务管理

### 管理后台

```bash
# 启动
systemctl start wingbank-admin

# 停止
systemctl stop wingbank-admin

# 重启
systemctl restart wingbank-admin

# 查看状态
systemctl status wingbank-admin

# 查看日志
journalctl -u wingbank-admin -f
```

### 机器人

```bash
# 启动
systemctl start wingbank-tgbot

# 停止
systemctl stop wingbank-tgbot

# 重启
systemctl restart wingbank-tgbot

# 查看状态
systemctl status wingbank-tgbot

# 查看日志
journalctl -u wingbank-tgbot -f
```

---

## ❓ 常见问题

### 1. 管理后台访问不了？

- 检查服务是否启动：`systemctl status wingbank-admin`
- 检查端口是否监听：`ss -ltnp | grep 8000`
- 检查防火墙是否开放端口
- 查看日志：`journalctl -u wingbank-admin -n 50`

### 2. 机器人不回复消息？

- 检查 Bot Token 是否正确
- 检查服务是否启动：`systemctl status wingbank-tgbot`
- 查看日志：`journalctl -u wingbank-tgbot -n 50`
- 确认机器人已经启动并正在长轮询

### 3. 数据库权限问题？

```bash
# 确保数据库文件可读写
chmod 664 /opt/wingbank-bot/shared.db
chown www-data:www-data /opt/wingbank-bot/shared.db
```

### 4. 怎么更新代码？

```bash
# 1. 上传新代码
# 2. 重启服务
systemctl restart wingbank-admin
systemctl restart wingbank-tgbot
```

### 5. 怎么修改管理员密码？

编辑 `/opt/wingbank-bot/admin/.env` 文件，修改 `ADMIN_PASSWORD`，然后重启服务。

---

## 📞 技术支持

如果遇到问题：
1. 先查看日志：`journalctl -u wingbank-admin -f`
2. 检查配置文件是否正确
3. 确认端口是否被占用

---

**部署完成后访问：**
- 管理后台：http://104.207.92.119:8000
- 管理员账号：admin / admin123（请尽快修改密码！）
