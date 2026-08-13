# WinVN Store 部署指南

> **域名**: winvn.store  
> **服务器**: ns13507.usc1.stableserver.net (185.181.254.173)  
> **账户**: wingdigi  
> **DNS**: ns1-4.mysecurecloudhost.com

---

## 目录结构

```
winvn.store/
├── /              → 前端 (React SPA + Landing Page)
├── /admin         → 后端管理 (FastAPI + React Admin)
└── /bot           → 机器人信息页
```

**服务架构**:
- **tgbot** (Go) - Telegram Bot 核心服务，long-polling 模式，后台运行
- **tgadmin** (Python/FastAPI + React) - 管理面板 + API + 前端静态文件
- **nginx** - 反向代理，统一 80/443 端口入口

---

## 前置准备

### 1. 系统要求
- Debian/Ubuntu 或兼容 systemd 的 Linux 发行版
- root 或 sudo 权限
- 已开放 80/443 端口

### 2. 安装依赖

```bash
# 更新系统
apt update && apt upgrade -y

# 安装基础工具
apt install -y git curl wget rsync nginx certbot python3-certbot-nginx

# 安装 Go (1.22+)
wget https://go.dev/dl/go1.22.0.linux-amd64.tar.gz
tar -C /usr/local -xzf go1.22.0.linux-amd64.tar.gz
echo 'export PATH=$PATH:/usr/local/go/bin' >> /etc/profile
source /etc/profile

# 安装 Node.js 20.x
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs

# 安装 Python 3 + venv
apt install -y python3 python3-venv python3-pip
```

### 3. DNS 配置

确保域名已解析到服务器 IP：
```
A     winvn.store          185.181.254.173
A     www.winvn.store      185.181.254.173
```

---

## 快速部署

### 方式一：自动部署脚本（推荐）

```bash
# 1. 上传代码到服务器
scp -r telegram-bot.zip root@185.181.254.173:/opt/
# 或 git clone
git clone <repo-url> /opt/telegram-bot

# 2. 解压（如果是 zip）
cd /opt && unzip telegram-bot.zip && cd telegram-bot

# 3. 运行部署脚本
bash deploy/deploy-winvn.sh
```

部署脚本会自动完成：
- 创建系统用户 (tgbot, tgadmin)
- 编译 tgbot Go 二进制
- 构建 React 前端
- 安装 Python 依赖
- 配置 systemd 服务
- 配置 nginx 反向代理
- 启动所有服务

### 方式二：手动部署

参见 `DEPLOY.md` 中的通用部署步骤，注意将域名替换为 `winvn.store`。

---

## 服务管理

### 查看服务状态

```bash
systemctl status tgbot.service
systemctl status tgadmin.service
```

### 查看日志

```bash
# 实时日志
journalctl -u tgbot.service -f
journalctl -u tgadmin.service -f

# 最近 100 行
journalctl -u tgbot.service -n 100 --no-pager
```

### 重启服务

```bash
systemctl restart tgbot.service
systemctl restart tgadmin.service
```

### 停止/启动服务

```bash
systemctl stop tgbot.service
systemctl start tgbot.service
```

---

## 配置文件

| 文件 | 说明 |
|------|------|
| `/etc/default/tgbot` | tgbot 环境变量配置 |
| `/etc/default/tgadmin` | tgadmin 环境变量配置 |
| `/etc/nginx/sites-available/winvn.store` | nginx 站点配置 |
| `/etc/systemd/system/tgbot.service` | tgbot systemd 服务 |
| `/etc/systemd/system/tgadmin.service` | tgadmin systemd 服务 |
| `/opt/shared.db` | 共享 SQLite 数据库 |

### 修改配置后

```bash
# 修改环境变量后
systemctl restart tgbot.service
systemctl restart tgadmin.service

# 修改 nginx 后
nginx -t && systemctl reload nginx

# 修改 systemd service 后
systemctl daemon-reload && systemctl restart <service>
```

---

## SSL/HTTPS 配置

使用 Certbot 自动配置 Let's Encrypt SSL：

```bash
certbot --nginx -d winvn.store -d www.winvn.store
```

Certbot 会自动：
- 申请 SSL 证书
- 配置 nginx HTTPS
- 设置自动续期

验证自动续期：
```bash
certbot renew --dry-run
```

---

## 更新部署

### 更新代码

```bash
cd /opt/telegram-bot
git pull  # 或重新上传

# 重新运行部署脚本（会覆盖代码并重启服务）
bash deploy/deploy-winvn.sh
```

### 仅更新 tgbot

```bash
cd /opt/tgbot
# 替换二进制文件
systemctl stop tgbot.service
cp new-tgbot /opt/tgbot/tgbot
chown tgbot:tgbot /opt/tgbot/tgbot
chmod 750 /opt/tgbot/tgbot
systemctl start tgbot.service
```

### 仅更新 tgadmin 前端

```bash
cd /opt/tgadmin/frontend
sudo -u tgadmin npm install
sudo -u tgadmin npm run build
systemctl restart tgadmin.service
```

### 仅更新 tgadmin 后端

```bash
cd /opt/tgadmin
sudo -u tgadmin .venv/bin/pip install -r requirements.txt
systemctl restart tgadmin.service
```

---

## 数据库

### 备份数据库

```bash
# 备份 SQLite 数据库
cp /opt/shared.db /opt/shared.db.backup_$(date +%Y%m%d_%H%M%S)
```

### 恢复数据库

```bash
systemctl stop tgbot.service tgadmin.service
cp /opt/shared.db.backup_YYYYMMDD_HHMMSS /opt/shared.db
chown tgbot:tgadmin /opt/shared.db
chmod 660 /opt/shared.db
systemctl start tgbot.service tgadmin.service
```

---

## 故障排查

### 服务无法启动

```bash
# 查看详细错误
journalctl -u tgbot.service -n 50 --no-pager
journalctl -u tgadmin.service -n 50 --no-pager

# 检查端口占用
ss -ltnp | grep -E ':(8000|8080|80|443)'

# 检查权限
ls -la /opt/tgbot/
ls -la /opt/tgadmin/
ls -la /opt/shared.db
```

### nginx 502 Bad Gateway

通常是后端服务未运行：
```bash
systemctl status tgadmin.service
# 如果未运行，查看日志并启动
```

### 机器人无响应

```bash
# 检查 bot 服务状态
systemctl status tgbot.service

# 检查 bot token 是否正确
cat /etc/default/tgbot | grep BOT_TOKEN

# 查看 bot 日志
journalctl -u tgbot.service -f
```

---

## 安全建议

1. **修改默认密码**
   ```bash
   # 编辑 tgadmin 配置
   nano /etc/default/tgadmin
   # 修改 TGADMIN_BOT_TOKEN 等敏感配置
   ```

2. **配置防火墙**
   ```bash
   ufw allow 22/tcp    # SSH
   ufw allow 80/tcp    # HTTP
   ufw allow 443/tcp   # HTTPS
   ufw enable
   ```

3. **定期备份数据库**
   ```bash
   # 添加 cron 任务，每天凌晨 3 点备份
   crontab -e
   # 添加：
   0 3 * * * cp /opt/shared.db /opt/backups/shared.db_$(date +\%Y\%m\%d).db
   ```

4. **限制 SSH 访问**
   - 使用密钥登录，禁用密码登录
   - 更改默认 SSH 端口

---

## 联系与支持

- 服务器面板: https://mysecurecloudhost.com
- 域名管理: 通过域名注册商管理 DNS
- 部署脚本: `deploy/deploy-winvn.sh`
- Nginx 配置: `deploy/nginx-winvn.conf`
