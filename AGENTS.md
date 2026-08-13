# Repository Guidelines

## Project Structure & Module Organization
This is a multi-component Telegram bot project sharing a central SQLite database (`./shared.db`).

- **`./tgbot`**: Go-based Telegram bot implementation. Uses `telebot.v3` and `modernc.org/sqlite` (CGO-free). Manages core bot logic, database migrations (in `./tgbot/migrations`), and long-polling.
- **`./admin`**: FastAPI-based admin panel using Jinja2 templates for server-side rendering. Focuses on bot management without a heavy JS framework.
- **`./tgadmin`**: Contains a FastAPI backend and a modern React/TypeScript frontend (in `./tgadmin/frontend`). The frontend is built with Vite, React Router, and styled with Bootstrap.
- **`./deploy`**: Centralized deployment scripts and `systemd` service configurations for both components.

## Build, Test, and Development Commands

### TGBot (Go)
- **Run**: `cd tgbot && go run main.go`
- **Build**: `cd tgbot && go build -o tgbot main.go`
- **Test**: `cd tgbot && go test ./...`
- **Single Test**: `cd tgbot && go test -v -run TestName ./path/to/pkg`

### Admin (Python/FastAPI)
- **Setup**: `cd admin && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
- **Run**: `cd admin && uvicorn app.main:app --reload`
- **Test**: `cd admin && pytest`

### TGAdmin Frontend (React/TypeScript)
- **Setup**: `cd tgadmin/frontend && npm install`
- **Run**: `cd tgadmin/frontend && npm run dev`
- **Build**: `cd tgadmin/frontend && npm run build`
- **Deploy**: `cd tgadmin/frontend && npm run deploy` (Vite build + Wrangler Pages)

## Coding Style & Naming Conventions
- **Go**: Idiomatic Go. CGO-free dependencies are preferred (e.g., `modernc.org/sqlite`).
- **Python**: FastAPI with Pydantic for validation. Follows PEP 8.
- **Frontend**: React with TypeScript. Components follow functional patterns. Styled with Bootstrap 5.

## Testing Guidelines
- **Go**: Unit tests are located alongside implementation files. Mocking is used for context and services (see `./tgbot/handlers/mock_context.go`).
- **Python**: Pytest is the preferred framework.

## Deployment Guidelines
Deployment is managed via `systemd` on Linux. Service templates and environment examples are located in `./deploy`. The frontend is deployed to Cloudflare Pages via Wrangler.
