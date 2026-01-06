# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

武林英雄离线助手 (Hero Hall Offline Assistant) - A full-stack automated game assistant for the "武林英雄" (Wulin Hero) browser game. The system automates daily tasks, arena challenges, dungeon runs, and scheduled activities for multiple game accounts.

## Architecture

### Backend (FastAPI Python)
- **main.py**: FastAPI application entry point with lifespan management, CORS, and endpoint registration
- **models.py**: Pydantic models for request/response validation
- **endpoints.py**: API endpoint handlers (~100KB file containing all REST endpoints)
- **job_scheduler.py**: Flexible job scheduling system supporting daily, hourly, weekly, and custom job types with ThreadPoolExecutor-based concurrency
- **character.py**: Core Character class representing a game account (~117KB) with methods for all game actions
- **hall_utils.py**: Hall (幻境) combat system with streaming support and thread management
- **pvehall.py**: PVE Hall challenge logic
- **command.py**: HTTP request wrapper for game server communication
- **auth_utils.py**: JWT token authentication using Azure Table Storage
- **cache_utils.py**: Caching layer for accounts and combat counts
- **job_utils.py**: Job execution functions (morning/night routines, dungeon runs, etc.)
- **job_execution_tracker.py**: Azure Table Storage integration for tracking job execution status
- **log.py**: User-specific logging with streaming handlers and file rotation
- **dungeon.py**: Dungeon challenge logic
- **cookie_extractor.py**: Playwright-based cookie extraction tool

### Frontend (React)
- **App.js**: Main application component (~72KB) orchestrating all UI state
- **components/**: Modular React components for each UI feature
  - Login.js, AccountList.js, OutputWindow.js, AddAccountDialog.js, SettingsDialog.js, LogViewerDialog.js, etc.
  - GlobalSettingsDialog.js: Job scheduler configuration UI
  - AdminPanel.js: Admin functionality for managing users
- **hooks/useStreaming.js**: Custom hook for Server-Sent Events (SSE) streaming
- **utils/api.js**: Centralized API client with axios
- **utils/logger.js**: Client-side logging utilities

### Data Storage
- **Azure Table Storage**:
  - `heroaccounts`: User's game accounts with cookies and settings
  - `herousers`: User registration and authentication data
  - `jobexecutions`: Job execution tracking and status
  - `jobsconfig`: Per-user job scheduler configuration

## Common Commands

### Backend Development
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
uvicorn main:app --reload --port 8081
```

### Frontend Development
```bash
cd frontend
npm install
npm start              # Development server (http://localhost:3000)
npm run start:local    # With local API (http://localhost:8081/api)
npm run start:prod     # With production API
npm run build          # Production build
npm test               # Run tests
```

### Environment Configuration
Backend requires `.env` file in `backend/` directory:
- `connection_string`: Azure Table Storage connection string
- `API_KEY`: API key for client requests
- `API_PORT`: Server port (default: 8081)
- `API_ENV`: "development" or "production"
- `SWAGGER_ENABLED`: "true"/"false" for Swagger UI
- `SMTP_*`: Email configuration for user registration

## Key Concepts

### Job Scheduler System
The job scheduler supports three job types:
- **DAILY**: Runs once per day at specified hour:minute (e.g., morning_routines, night_routines)
- **HOURLY**: Runs every hour at specified minute (e.g., cache refresh)
- **WEEKLY**: Runs on specific day of week (e.g., monday_routines, wednesday_routines)

Jobs are configured per-user in Azure Table Storage and can be enabled/disabled with custom schedules. The scheduler executes missed jobs on restart in production mode.

### Hall Combat (幻境挑战)
The hall combat system uses Server-Sent Events (SSE) for real-time progress streaming:
- Multiple accounts can challenge halls simultaneously
- Thread management prevents concurrent requests for the same account
- Supports 6 hall types: 封神异志, 平倭群英传, 武林群侠传, 三国鼎立, 乱世群雄, 绝代风华
- Each hall can have custom floor-by-floor strategies

### Streaming Architecture
- Backend uses `user_log_manager.get_streaming_handler(username)` for per-user log queues
- Frontend `useStreaming.js` hook connects to `/api/hall_combat_stream` endpoint
- Logs are queued in memory and sent as SSE events to connected clients

### Character Class
The `Character` class in `character.py` encapsulates all game actions:
- Parses HTML responses from game server using BeautifulSoup
- Manages cookie-based authentication
- Implements combat, training, item usage, and all game operations

### Account Settings Structure
Each account has optional settings:
- `hall_settings`: Per-hall challenge strategies (floor orders, skill configs, special flags)
- `common_settings`: Shared settings like duel target
- `dungeon_settings`: List of dungeon configurations
- `duel_dungeon_settings`: Cross-server dungeon configurations

## Important Notes

### Azure Table Operations
- When updating Azure Table data, always show changes before committing
- Use `upsert_entity` for both create and update operations
- Table keys: `PartitionKey` = username, `RowKey` = entity identifier

### Cookie Management
- Game cookies follow format: `svr={server_url};weeCookie={cookie_value}`
- Cookies must be refreshed periodically (use `refresh_cache` endpoint)
- The cookie_extractor.py can extract cookies using Playwright automation

### Concurrency Control
- `request_lock` and `active_requests` prevent duplicate requests for same account
- `hall_combat_lock` protects thread management data structures
- ThreadPoolExecutor bounds maximum concurrent job workers

### Development vs Production
- Production mode (`API_ENV=production`): Enables job scheduler, executes missed jobs
- Development mode: Job scheduler runs but doesn't auto-execute missed jobs
- Swagger UI auto-disabled in production

### File Path Handling
- Use double backslashes `\\` or forward slashes `/` for Windows paths
- Example: `venv\\Scripts\\python.exe` or `venv/Scripts/python.exe`
