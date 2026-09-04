# Wing Bank 线上当前版本导出

导出时间：2026-09-05（来源服务器 103.138.189.69 / cPanel 账户 winvnsto）

## 目录
- `backend/`  —— FastAPI 管理/接口后端（线上运行目录 wingbank-admin，已剔除 venv、shared.db 资金库、.env、VAPID/Firebase 私钥、日志与备份）
- `webapp/`   —— 线上前端（public_html/app：React 构建产物 assets + 自定义页 my-qr/scan/pin 等），已剔除全部 .bak/.previous 备份与测试大图
- `webroot/`  —— Apache 反代/重写配置（api.php 反代到 127.0.0.1:8081；根与 /app 的 .htaccess，改名为 .txt 便于查看）

## 安全说明
本仓库为公开仓库，**不含**任何真实资金数据库、客户 KYC、PIN、机器人 Token 或服务账号私钥；
本地运行请复制 `backend/.env.example` 为 `.env` 自行填写。
