# Cloudflare Tunnel 部署说明

这里以 `tgadmin` 管理后台为例，并顺带说明 `tgbot` 机器人如何在服务器内运行。整体方案是：

- `tgbot`：在服务器上直接运行，使用 Telegram Bot API 长轮询，通常不需要通过 Cloudflare 暴露。
- `tgadmin`：在服务器上监听 `127.0.0.1:8000`，再通过 Cloudflare Tunnel 暴露到公网。

## 1. 服务器端配置：tgadmin

进入 `tgadmin/` 目录，安装依赖：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

编辑 `.env`：

```bash
TGADMIN_HOST=127.0.0.1
TGADMIN_PORT=8000
TGADMIN_BOT_TOKEN=your-bot-token
TGADMIN_CORS_ORIGINS=https://wingdigital.fit,https://www.wingdigital.fit
TGADMIN_DEBUG=false
```

启动服务：

```bash
bash ../deploy/start-tgadmin.sh
```

这会让服务监听 `127.0.0.1:8000`，便于由 Cloudflare Tunnel 转发。

> 注意：本项目已配置将 `tgadmin/frontend/dist` 中构建后的管理后台前端静态资源作为 `/admin` 路径提供，根路径 `/` 提供一个简单的首页链接到管理后台。若你使用本仓库部署，请先在 `tgadmin/frontend` 下运行 `npm run build`。
>
> 如果你的域名当前仍使用 Namecheap 的 nameserver（例如 `1dns1.namecheaphosting.com`, `2dns2.namecheaphosting.com`），则域名还没有接入 Cloudflare，Cloudflare Tunnel 无法生效。请先将 `wingdigital.fit` 的 nameserver 改成 Cloudflare 提供的 nameserver，并等待 DNS 生效。
>
> 在 Namecheap 域名管理中，将 `wingdigital.fit` 的 nameserver更改为 Cloudflare 提供的两个 nameserver（通常类似 `abby.ns.cloudflare.com` 和 `bill.ns.cloudflare.com`），然后等待数分钟到数小时生效。
>
> 另外，建议使用 WHOIS 或 Namecheap 控制面板确认域名状态是否正常。如果域名仍显示 `clientHold`、`pendingTransfer` 或其他暂停状态，则域名无法正常解析，即便 nameserver 已改成 Cloudflare 也需要先解除该状态。

## 2. 服务器端配置：tgbot

进入 `tgbot/` 目录，配置环境变量：

```bash
cp .env.example .env
```

编辑 `.env`：

```bash
BOT_TOKEN=your_bot_token_here
DATABASE_PATH=../shared.db
MIGRATIONS_DIR=./migrations
BOT_NAME=wing-bank
BOT_VERSION=dev
```

构建并运行机器人：

```bash
bash ../deploy/start-tgbot.sh
```

这一步不需要暴露到 Cloudflare，机器人通过 Telegram Bot API 与 Telegram 服务器直接通信。

## 3. 安装 Cloudflare Tunnel

在服务器上安装 `cloudflared`，然后创建一个隧道：

```bash
sudo useradd --system --home-dir /var/lib/cloudflared --shell /usr/sbin/nologin cloudflared 2>/dev/null || true
sudo mkdir -p /etc/cloudflared /var/lib/cloudflared
sudo chown -R cloudflared:cloudflared /var/lib/cloudflared

cloudflared tunnel login
cloudflared tunnel create tgadmin
```

将仓库里的模板文件复制到服务器系统目录：

```bash
sudo cp ../deploy/cloudflared.yml.example /etc/cloudflared/config.yml
sudo cp ../deploy/cloudflared.default /etc/default/cloudflared
sudo cp ../deploy/cloudflared.service /etc/systemd/system/cloudflared.service
```

### 3.1 在 Cloudflare Dashboard 中配置域名

1. 登录 Cloudflare 控制台，选择你的域名 `wingdigital.fit`。
2. 进入 `DNS` 页面，确认已经将当前 DNS 记录改为 Cloudflare nameserver 提供的两条 nameserver。如果还没有改，请先在 Namecheap 域名管理中完成 nameserver 修改，然后再回来刷新 Cloudflare 仪表盘。
3. 进入 `Traffic > Cloudflare Tunnel`（或 `Zero Trust > Access > Tunnels`，具体位置因 Cloudflare 控制面板版本而异）。
4. 找到你创建的 `tgadmin` 隧道，点击 `Public hostnames` 或 `Add hostname`。
5. 添加主机名：
   - `wingdigital.fit`
   - 可选：`www.wingdigital.fit`（如果你希望带 www 也可访问）
   - 将 `Service` 设置为 `http://127.0.0.1:8000`
6. 保存后，Cloudflare 会在 DNS 中为该主机名生成一个代理记录。
7. 如果你的域名根记录已经通过 Cloudflare 托管，`wingdigital.fit` 的 DNS 显示应为 `A` 记录或 `CNAME`，并且云朵状态为“已代理”（橙色）。

> 提示：对于根域名 `wingdigital.fit`，Cloudflare 会自动处理 CNAME 扁平化；你无需手动设置 A 记录到某个固定 IP。只要在 Cloudflare Dashboard 里为隧道创建了公开主机名，并且 nameserver 已正确指向 Cloudflare，域名就可以走隧道代理访问。

### 3.2 如果你使用的是 Cloudflare DNS 记录

如果你没有使用 Cloudflare Tunnel 的公开主机名方式，也可以在 `DNS` 中创建一个受代理的记录：

- 类型：`CNAME`
- 名称：`@` 或留空
- 目标：由 Cloudflare Tunnel 生成的隧道域名（例如 `xxxx.cloudflare-tunnel.com`）
- 状态：代理（橙色云）

然后在 Cloudflare Tunnel 的 `Ingress Rules` 中继续使用 `hostname: wingdigital.fit` 指向 `http://127.0.0.1:8000`。

## 4. 编辑 cloudflared 配置

编辑 `/etc/cloudflared/config.yml`，把 `your-tunnel-id` 替换为实际隧道 ID，并确保 `hostname` 设置为 `wingdigital.fit`：

```yaml
tunnel: your-tunnel-id
credentials-file: /var/lib/cloudflared/your-tunnel-id.json
ingress:
  - hostname: wingdigital.fit
    service: http://127.0.0.1:8000
  - hostname: www.wingdigital.fit
    service: http://127.0.0.1:8000
  - service: http_status:404
```

如果你只需要 `wingdigital.fit`，也可以省略 `www.wingdigital.fit`。

然后重启 cloudflared：

```bash
sudo systemctl daemon-reload
sudo systemctl restart cloudflared.service
```


## 4. 使用 systemd 管理两个服务

可以直接使用仓库里的服务模板与默认值文件：

```bash
sudo mkdir -p /etc/default
sudo cp ../deploy/tgadmin.service /etc/systemd/system/tgadmin.service
sudo cp ../deploy/tgbot.service /etc/systemd/system/tgbot.service
sudo cp ../deploy/tgadmin.default /etc/default/tgadmin
sudo cp ../deploy/tgbot.default /etc/default/tgbot
sudo systemctl daemon-reload
sudo systemctl enable --now tgadmin tgbot cloudflared.service
```

注意：模板中的路径需要替换为你服务器上的实际目录；例如 `/opt/tgadmin`、`/opt/tgbot`、`/opt/shared.db`。

## 5. 验证

访问 Cloudflare 域名，例如：

```text
https://wingdigital.fit/           # 前端
https://wingdigital.fit/admin     # 管理后台
https://wingdigital.fit/bot       # 机器人说明页
```

若前端能正常打开，并且 API 请求返回成功，则部署完成。

## 6. 检查域名解析与连接

如果域名无法访问，先检查 `wingdigital.fit` 的 DNS 与 HTTP 连接。你可以在服务器上运行：

```bash
bash ../deploy/check-domain.sh wingdigital.fit
```

该脚本会显示当前 nameserver、A 记录，以及 `http://` / `https://` 的连接结果，帮助判断域名是否已经正确指向你的 Cloudflare Tunnel 或服务器。
