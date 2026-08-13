# Wing Bank 部署指南

## 架构

```
                    ┌─────────────────┐
                    │   Nginx :443    │  (TLS 终止)
                    └────────┬────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
    ┌───────▼──────┐ ┌──────▼───────┐ ┌──────▼───────┐
    │  tgadmin     │ │   admin      │ │   tgbot      │
    │  :8000       │ │   :8080      │ │  (无端口)    │
    │  FastAPI+React│ │  FastAPI+Jinja│ │  Go 机器人   │
    └──────────────┘ └──────────────┘ └──────────────┘
```

## 端口分配

| 服务 | 端口 | 说明 |
|------|------|------|
| Nginx | 80/443 | 对外入口，TLS |
| tgadmin | 8000 | API + React 前端 |
| admin | 8080 | 管理后台 (Jinja2) |
| tgbot | - | Telegram 机器人，不暴露端口 |

## 快速部署

### 1. 修改配置

编辑 `deploy/install.sh` 顶部的配置：

```bash
DOMAIN="your-domain.com"
EMAIL="admin@your-domain.com"
GIT_REPO="git@github.com:mrkk9919/-adminwin.git"
```

### 2. 运行部署脚本

```bash
# CentOS / Ubuntu / Debian
sudo bash deploy/install.sh
```

### 3. 配置环境变量

编辑三个 `.env` 文件：

```bash
sudo nano /opt/wingbank/tgbot/.env      # Bot Token
sudo nano /opt/wingbank/admin/.env      # 管理后台账号密码
sudo nano /opt/wingbank/tgadmin/.env    # API 配置
```

### 4. 重启服务

```bash
sudo systemctl restart tgbot admin tgadmin
```

## 手动部署

### 安装依赖

**CentOS Stream 10:**
```bash
sudo dnf install -y git python3 python3-pip python3-venv golang nginx certbot python3-certbot-nginx
```

**Ubuntu 22.04+:**
```bash
sudo apt install -y git python3 python3-pip python3-venv golang nginx certbot python3-certbot-nginx
```

### 部署代码

```bash
sudo mkdir -p /opt/wingbank
sudo git clone git@github.com:mrkk9919/-adminwin.git /opt/wingbank
```

### 编译 Go 机器人

```bash
cd /opt/wingbank/tgbot
go mod download
CGO_ENABLED=1 go build -o tgbot .
```

### 配置 Python 环境

```bash
# Admin panel
cd /opt/wingbank/admin
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
deactivate

# TGAdmin
cd /opt/wingbank/tgadmin
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
deactivate
```

### 配置 systemd

```bash
sudo cp /opt/wingbank/deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable tgbot admin tgadmin
```

### 配置 Nginx + TLS

```bash
# 先配置 HTTP 用于证书验证
sudo cp /opt/wingbank/deploy/nginx/wingbank-http.conf /etc/nginx/conf.d/wingbank.conf
sudo sed -i 's/YOUR_DOMAIN/your-domain.com/g' /etc/nginx/conf.d/wingbank.conf
sudo nginx -t && sudo systemctl restart nginx

# 获取证书
sudo certbot certonly --webroot -w /var/www/certbot -d your-domain.com -d www.your-domain.com

# 切换到 HTTPS 配置
sudo cp /opt/wingbank/deploy/nginx/wingbank-ssl.conf /etc/nginx/conf.d/wingbank.conf
sudo sed -i 's/YOUR_DOMAIN/your-domain.com/g' /etc/nginx/conf.d/wingbank.conf
sudo nginx -t && sudo systemctl restart nginx
```

### 启动服务

```bash
sudo systemctl start tgbot admin tgadmin
```

## 常用命令

```bash
# 查看服务状态
sudo systemctl status tgbot admin tgadmin

# 查看日志
sudo journalctl -u tgbot -f
sudo journalctl -u admin -f
sudo journalctl -u tgadmin -f

# 重启服务
sudo systemctl restart tgbot admin tgadmin

# Nginx 重载
sudo nginx -t && sudo systemctl reload nginx

# 证书续期测试
sudo certbot renew --dry-run
```

## 安全建议

1. **修改默认密码** - admin/.env 中的 ADMIN_PASSWORD
2. **修改 JWT_SECRET** - 使用随机字符串
3. **Bot Token 保密** - 不要提交到 git
4. **防火墙** - 只开放 80/443 端口
5. **定期更新** - `sudo dnf update` 或 `sudo apt upgrade`
6. **数据库备份** - 定期备份 shared.db

## 故障排查

### 服务启动失败
```bash
sudo journalctl -u tgbot -n 50 --no-pager
```

### Nginx 502 Bad Gateway
检查后端服务是否运行：
```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8080/
```

### 证书续期失败
```bash
sudo certbot renew --dry-run
sudo systemctl status certbot-renew.timer
```
