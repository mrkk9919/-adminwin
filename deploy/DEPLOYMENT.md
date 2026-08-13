TGAdmin 与 TGBot 统一部署说明

目标

- 提供在 Linux（systemd）服务器上部署 tgadmin（FastAPI 管理面板）与 tgbot（Go 二进制）的一套统一、可复用步骤。
- 包含 systemd 单元位置、环境变量文件、日志查看、常见注意事项、反向代理示例以及数据库/权限说明。

假设

- 目标主机运行 systemd（例如 Debian/Ubuntu/CentOS/RHEL/Fedora）
- 有 sudo 权限用于复制文件、创建用户、写入 /etc/systemd/system/ 等位置
- 源代码已在构建主机或目标主机（/opt 下）可用
- 共享 SQLite 数据库文件放在一个受限目录（示例：/var/lib/tg/shared.db）

文件与模板位置（仓库内）

- systemd 单元：deploy/tgadmin.service（已有）
- systemd 单元：deploy/tgbot.service（已有）
- 环境示例：deploy/tgadmin.env.example
- 环境示例：deploy/tgbot.env.example
- 本说明文档：deploy/DEPLOYMENT.md

常用路径（推荐，可按需修改）

- /opt/tgadmin         # tgadmin 源码或部署目录
- /opt/tgadmin/.venv   # Python 虚拟环境（建议）
- /opt/tgbot           # tgbot 编译后的二进制及文件
- /etc/default/tgadmin # systemd EnvironmentFile，存放 TGAdmin 环境变量
- /etc/default/tgbot   # systemd EnvironmentFile，存放 TGBot 环境变量
- /etc/tgbot/config.yaml # （可选）tgbot 的配置文件位置
- /var/lib/tg/shared.db # 共享 SQLite 数据库（tgbot 与 tgadmin 共同使用）

1) 基本安全与用户

- 为服务分别建立系统用户，限制权限：
  sudo useradd --system --no-create-home --shell /usr/sbin/nologin tgadmin
  sudo useradd --system --no-create-home --shell /usr/sbin/nologin tgbot

- 创建 /var/lib/tg 并设置权限：
  sudo mkdir -p /var/lib/tg
  sudo chown tgadmin:tgbot /var/lib/tg
  sudo chmod 750 /var/lib/tg

  说明：若 tgadmin 和 tgbot 需要同时读写 shared.db，保证文件属主或组配置允许访问（例如属主 tgadmin，组 tgbot，或反之），并根据需要设置 umask/权限。

2) 部署 TGAdmin（FastAPI）

步骤概览：创建虚拟环境、安装依赖、配置环境变量、配置 systemd、可选使用 nginx 反向代理。

- 在目标机上：
  sudo mkdir -p /opt/tgadmin
  sudo chown -R deployuser:deployuser /opt/tgadmin   # 用于复制源码或 git clone

- 复制或拉取代码到 /opt/tgadmin（或通过 CI/CD）：
  git clone <repo> /opt/tgadmin

- 创建 Python 虚拟环境并安装依赖（在 /opt/tgadmin 下）：
  python3 -m venv .venv
  . .venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt

- 配置环境文件
  将仓库中的 deploy/tgadmin.env.example 拷贝为 /etc/default/tgadmin，编辑实际值：
  sudo cp deploy/tgadmin.env.example /etc/default/tgadmin
  sudo chown root:root /etc/default/tgadmin
  sudo chmod 640 /etc/default/tgadmin

- 检查并调整 systemd 单元（deploy/tgadmin.service）
  sudo cp deploy/tgadmin.service /etc/systemd/system/tgadmin.service
  # 编辑下面两行（示例）
  # WorkingDirectory=/opt/tgadmin
  # ExecStart=/opt/tgadmin/.venv/bin/python -m app.main

- 启用并启动服务：
  sudo systemctl daemon-reload
  sudo systemctl enable --now tgadmin.service
  sudo systemctl status tgadmin.service
  sudo journalctl -u tgadmin -f

- 可选：使用 nginx 作为反向代理（推荐用于 TLS、负载均衡、静态文件）：
  # 简要示例（Ubuntu /etc/nginx/sites-available/tgadmin.conf）
  server {
      listen 80;
      server_name admin.example.com;

      location / {
          proxy_pass http://127.0.0.1:8000;
          proxy_set_header Host $host;
          proxy_set_header X-Real-IP $remote_addr;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_set_header X-Forwarded-Proto $scheme;
      }
  }

  然后启用站点并重载 nginx：
  sudo ln -s /etc/nginx/sites-available/tgadmin.conf /etc/nginx/sites-enabled/
  sudo nginx -t && sudo systemctl reload nginx

3) 部署 TGBot（Go）

说明：tgbot 为长轮询 bot，建议以单个长期运行的 systemd 服务进程运行。

- 在目标机创建目录并设置权限：
  sudo mkdir -p /opt/tgbot
  sudo chown deployuser:deployuser /opt/tgbot

- 构建二进制（在构建主机或目标机）：
  cd /path/to/repo/tgbot
  # 推荐在干净的 Linux 构建环境下构建：
  GOOS=linux GOARCH=amd64 CGO_ENABLED=0 go build -o /opt/tgbot/tgbot .
  sudo chown root:tgbot /opt/tgbot/tgbot
  sudo chmod 750 /opt/tgbot/tgbot

- 配置 env / config
  复制示例并编辑：
  sudo mkdir -p /etc/tgbot
  sudo cp deploy/tgbot.env.example /etc/default/tgbot
  # 如果项目使用 /etc/tgbot/config.yaml，请将其放到 /etc/tgbot/config.yaml 并根据 .env.example 填写敏感值
  sudo chown root:root /etc/default/tgbot
  sudo chmod 640 /etc/default/tgbot

- 检查 systemd 单元（deploy/tgbot.service）
  sudo cp deploy/tgbot.service /etc/systemd/system/tgbot.service
  # 确认 ExecStart 指向 /opt/tgbot/tgbot，或带上 --config /etc/tgbot/config.yaml

- 启用并启动：
  sudo systemctl daemon-reload
  sudo systemctl enable --now tgbot.service
  sudo systemctl status tgbot.service
  sudo journalctl -u tgbot -f

4) 共享数据库（SQLite）与权限

- SQLite 文件示例位置：/var/lib/tg/shared.db
- 建议：将 shared.db 放在 /var/lib/tg，并设置合适的属主/属组和权限：
  sudo chown tgadmin:tgbot /var/lib/tg/shared.db
  sudo chmod 660 /var/lib/tg/shared.db

- 如果同时有多个进程（tgadmin + tgbot）访问 SQLite，确保使用支持并发访问的 SQLite 驱动，并测试并发场景（本项目使用 modernc.org/sqlite，注意锁与 WAL 模式）。

5) 日志与监控

- 使用 journalctl 查看 systemd 日志：
  sudo journalctl -u tgadmin -f
  sudo journalctl -u tgbot -f

- 建议将关键日志推送到集中的日志系统（ELK/Fluentd/Graylog）或使用 systemd 的 Forwarding 设置。

- 推荐设置 systemd 的 Restart=on-failure（或 always）和合理的 RestartSec，防止瞬时重试风暴。

6) 升级与回滚

- 升级 tgbot：
  1. 在构建服务器构建新二进制并上传到目标路径为 /opt/tgbot/tgbot.new
  2. sudo systemctl stop tgbot
  3. sudo mv /opt/tgbot/tgbot /opt/tgbot/tgbot.old
  4. sudo mv /opt/tgbot/tgbot.new /opt/tgbot/tgbot
  5. sudo chown root:tgbot /opt/tgbot/tgbot && sudo chmod 750 /opt/tgbot/tgbot
  6. sudo systemctl start tgbot
  7. 检查日志，若异常可恢复旧版本（反向 mv）

- 升级 tgadmin：
  1. 在 /opt/tgadmin 中拉取新代码，更新依赖（在虚拟环境中 pip install -r requirements.txt）
  2. sudo systemctl restart tgadmin
  3. 如需回退，使用 git checkout 到旧的 commit 并重启服务

7) 常见问题与注意事项

- 权限问题：shared.db 权限不当会导致服务启动但无法访问数据库：检查 journalctl 日志并确认文件访问错误。
- 防火墙：如果需要外网访问 tgadmin（通过 nginx/TLS），开放 80/443；tgbot 为出站访问 Telegram API（TCP 443）需允许出站流量。
- SELinux/AppArmor：若启用，请为服务单元配置合适的策略（或在调试时短期禁用策略以验证权限问题）。
- 时区：确保服务器时区设置一致（有助于日志与心跳时间对齐）。

8) 可选：systemd 模板与监测

- 若需要运行多个 bot 实例（不同 token 或不同逻辑），可使用 systemd 模板文件 tgbot@.service，使用实例名传递不同的 EnvironmentFile 或参数。
- 若需要更强的进程监测，可配置 systemd Watchdog（WatchdogSec + NotifyAccess=all）并在程序中触发 sd_notify 心跳（需要额外代码支持）。

结束语

本说明旨在作为生产部署的统一参考。实际部署可根据组织安全策略（secrets 管理、容器化、配置管理工具如 Ansible/Chef）调整。若需要，将帮助把这些步骤改写为 Ansible playbook 或 Docker Compose / systemd-nspawn 配置。
