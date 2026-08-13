部署说明（统一）

本文档给出在常见 Linux 服务器上部署 tgbot（Go 二进制）和 tgadmin（FastAPI/Python）的标准步骤、systemd 服务模板和常见运维建议。假设使用 Debian/Ubuntu 或兼容的 systemd 发行版。

1. 前置准备
- 创建系统用户（将服务限制为非交互用户）：
  sudo useradd --system --no-create-home --shell /usr/sbin/nologin tgbot
  sudo useradd --system --no-create-home --shell /usr/sbin/nologin tgadmin

- 创建目录并设置权限：
  sudo mkdir -p /opt/tgbot /etc/tgbot
  sudo mkdir -p /opt/tgadmin /etc/tgadmin
  sudo chown -R tgbot:tgbot /opt/tgbot /etc/tgbot
  sudo chown -R tgadmin:tgadmin /opt/tgadmin /etc/tgadmin

2. 部署 TGBot（Go 二进制）
- 将编译好的二进制上传到 /opt/tgbot/tgbot，并确保可执行：
  sudo cp ./tgbot /opt/tgbot/tgbot
  sudo chown tgbot:tgbot /opt/tgbot/tgbot
  sudo chmod 750 /opt/tgbot/tgbot

- 放置配置文件：/etc/tgbot/config.yaml（或你项目使用的格式）。如果使用 /etc/default/tgbot，复制示例：
  sudo cp deploy/tgbot.env.example /etc/default/tgbot
  sudo chown root:root /etc/default/tgbot
  sudo chmod 640 /etc/default/tgbot

- systemd 单元：
  将 deploy/tgbot.service 复制到 /etc/systemd/system/tgbot.service：
  sudo cp deploy/tgbot.service /etc/systemd/system/tgbot.service
  （如需修改 WorkDir/ExecStart 或用户，请在复制后编辑）

- 启动并启用服务：
  sudo systemctl daemon-reload
  sudo systemctl enable --now tgbot.service
  sudo systemctl status tgbot.service
  日志查看： sudo journalctl -u tgbot.service -f

3. 部署 TGAdmin（FastAPI / Python）
- 克隆或复制代码到 /opt/tgadmin：
  sudo rsync -a ./tgadmin/ /opt/tgadmin/
  sudo chown -R tgadmin:tgadmin /opt/tgadmin

- 创建并激活虚拟环境（在服务器上以 root 或具有 sudo 的用户操作）：
  sudo -u tgadmin bash -c "python3 -m venv /opt/tgadmin/.venv && /opt/tgadmin/.venv/bin/pip install --upgrade pip setuptools"
  sudo -u tgadmin /opt/tgadmin/.venv/bin/pip install -r /opt/tgadmin/requirements.txt

- 配置环境变量：
  将 deploy/tgadmin.env.example 的内容复制到 /etc/default/tgadmin 并根据情况填写（DB URL、TG token 等）：
  sudo cp deploy/tgadmin.env.example /etc/default/tgadmin
  sudo chown root:root /etc/default/tgadmin
  sudo chmod 640 /etc/default/tgadmin

  注意：项目根目录 tgadmin/.env.example 也可用于本地开发，但 systemd 使用 /etc/default/tgadmin 更适合运维。

- 迁移/初始化数据库（如果需要）：
  以 tgadmin 用户运行项目提供的迁移脚本或命令，例如：
  sudo -u tgadmin /opt/tgadmin/.venv/bin/python /opt/tgadmin/manage.py migrate
  （具体命令依项目而定）

- systemd 单元：
  sudo cp deploy/tgadmin.service /etc/systemd/system/tgadmin.service
  编辑 /etc/systemd/system/tgadmin.service 中的 WorkDir、ExecStart 或 EnvironmentFile（若必要）

  - 你也可以运行仓库中的自动部署脚本： `deploy/deploy-wingdigital.sh`。
    请在服务器上以 root 身份执行，必要时先设置环境变量覆盖默认值。
- 启动并启用服务：
  sudo systemctl daemon-reload
  sudo systemctl enable --now tgadmin.service
  sudo systemctl status tgadmin.service
  日志查看： sudo journalctl -u tgadmin.service -f

4. 反向代理（可选，推荐在公网使用 Nginx / Traefik）：
- Nginx 示例（将请求代理到本地 127.0.0.1:8000）：
  server {
    listen 80;
    server_name admin.example.com;

    location / {
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto $scheme;
      proxy_pass http://127.0.0.1:8000;
    }
  }

- 强烈建议启用 HTTPS（Certbot / Let's Encrypt）并限制访问（CORS / 防火墙）

5. 常见维护操作
- 更新 tgbot 二进制：
  1) 停止服务： sudo systemctl stop tgbot.service
  2) 上传新二进制并替换 /opt/tgbot/tgbot
  3) 修正权限： sudo chown tgbot:tgbot /opt/tgbot/tgbot && sudo chmod 750 /opt/tgbot/tgbot
  4) 启动并检查： sudo systemctl start tgbot.service && sudo journalctl -u tgbot.service -f

- 更新 tgadmin 应用：
  1) 进入 /opt/tgadmin，拉取/复制新代码
  2) 以 tgadmin 用户更新依赖： sudo -u tgadmin /opt/tgadmin/.venv/bin/pip install -r requirements.txt
  3) 运行迁移（如需）
  4) 重启服务： sudo systemctl restart tgadmin.service

6. 权限与安全建议
- 将 service 用户（tgbot/tgadmin）限制为 system 用户，不允许交互登录。
- 配置文件与密钥放在 /etc/tgbot/ 或 /etc/tgadmin/，权限设为 640 并由 root:service-user 拥有。
- 生产环境推荐使用外部数据库（Postgres）替代 SQLite，防止并发和数据丢失问题。
- 若需要高可用或负载均衡，请放到容器或使用 process supervisor +反向代理 + 多实例。

7. 故障排查
- 查看 service 状态： sudo systemctl status <service>
- 实时日志： sudo journalctl -u <service> -f
- 检查端口： sudo ss -ltnp | grep <port>
- 检查权限错误：systemd 日志通常会显示权限/文件未找到等问题

---
这些步骤为通用建议。若需要把 unit 文件、env 文件自动化为配置管理（Ansible、Salt、Terraform），可以把本目录下的 deploy/*.service 和 deploy/*.env.example 用作模板。
