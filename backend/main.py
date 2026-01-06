# Standard library imports
import os
import threading
from contextlib import asynccontextmanager

# Third-party imports
from fastapi import FastAPI, HTTPException, Request, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from azure.data.tables import TableServiceClient
import uvicorn
from dotenv import load_dotenv

# Load environment variables from .env BEFORE importing modules that use them
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    load_dotenv(env_path, override=True)
else:
    # Try to find .env file automatically
    from dotenv import find_dotenv
    found_env = find_dotenv()
    if found_env:
        load_dotenv(found_env, override=True)

# Project imports
from job_scheduler import JobScheduler, setup_scheduler_jobs, scheduler_worker
from log import setup_logging, user_log_manager
from endpoints import (
    get_scheduler_status, health_check,
    register, login, login_with_google, refresh_token, get_accounts, add_account, get_info, get_duel_info,
    connection_status, clear_stream_queue, get_log_files,
    get_log_file_content, stop_combat, delete_account, refresh_cache, clear_cache,
    cache_status, get_user_settings, get_jobs_table, get_job_scheduler_status,
    set_job_settings, debug_user_settings, clear_active_requests, buy_combat_count,
    execute_job_manually, execute_command, olympics, zongheng_challenge, buy_duel_medal, get_fan_badges, exchange_fan_badge,
    auto_gift, lottery, extract_cookies, extract_cookies_interactive,
    get_all_players, get_player_accounts, toggle_user_status,
    get_job_status, initiate_shutdown, get_shutdown_status,
    open_browser_with_cookies
)
from hall_utils import hall_combat_stream, resume_stream
from config_utils import save_jobs_config
from auth_utils import verify_token
from job_execution_tracker import initialize_job_executions_table, get_missed_jobs
from datetime import datetime
import cache_utils
import auth_utils
import hall_utils
import request_utils
import endpoints

# =============================================================================
# Configuration and Environment Setup
# =============================================================================

# Setup logging
logger = setup_logging()

# Disable Swagger UI in production or when specified
SWAGGER_ENABLED = os.getenv('SWAGGER_ENABLED', 'true').lower() == 'true'
API_ENV = os.getenv('API_ENV') or 'development'

# Auto-disable Swagger in production
if API_ENV == 'production':
    SWAGGER_ENABLED = False

# Global job scheduler - will be initialized in lifespan event
job_scheduler = None
scheduler_thread = None

# Graceful shutdown state management
shutdown_requested = threading.Event()
scheduler_paused = False
scheduler_paused_lock = threading.Lock()
active_jobs = {}  # {execution_id: {username, job_id, start_time, future}}
active_jobs_lock = threading.Lock()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events"""
    global job_scheduler, scheduler_thread
    
    # Log Swagger status
    if SWAGGER_ENABLED:
        logger.info("Swagger UI enabled - available at /docs")
    else:
        logger.info("Swagger UI disabled")
    
    # Initialize job execution tracker
    initialize_job_executions_table(connection_string)
    
    # Startup - initialize job scheduler first
    if job_scheduler is None:
        job_scheduler = JobScheduler(connection_string=connection_string, logger=logger)
        # Set shutdown globals in job_scheduler module
        from job_scheduler import set_shutdown_globals
        set_shutdown_globals(shutdown_requested, scheduler_paused, scheduler_paused_lock, active_jobs, active_jobs_lock)
        setup_scheduler_jobs(job_scheduler)
    
    # Only initialize job records and execute missed jobs in production environment
    if API_ENV == 'production':
        # Print daily job summary on startup
        from job_execution_tracker import print_daily_job_summary, check_job_records_exist_for_date, initialize_daily_job_records
        from utils import get_china_now
        
        china_now = get_china_now()
        
        # Print summary of today's jobs
        # print_daily_job_summary(china_now)
        
        # Check if job records exist for today, if not initialize them
        records_exist = check_job_records_exist_for_date(china_now)
        
        if not records_exist:
            logger.info("No job execution records found for today, initializing...")
            # Initialize records for today - past jobs will be marked as completed (assumed successful)
            initialize_daily_job_records(job_scheduler, china_now)
            # Print summary again after initialization
            # logger.info("Job records initialized. Summary:")
            # print_daily_job_summary(china_now)
        else:
            logger.info("Job execution records exist for today, checking for missed jobs...")
            # Check for missed jobs and execute them
            try:
                missed_jobs = get_missed_jobs()
                if missed_jobs:
                    logger.info(f"Found {len(missed_jobs)} missed jobs, executing them...")
                    from job_execution_tracker import update_job_execution_status
                    from job_scheduler import JobType
                    
                    for entity in missed_jobs:
                        username = entity['PartitionKey']
                        job_id = entity['job_id']
                        job_type = entity['job_type']
                        scheduled_time_str = entity.get('scheduled_time')
                        execution_id = entity['RowKey']
                        
                        # Mark old 'running' jobs as failed if they're too old (> 2 hours)
                        if entity['status'] == 'running':
                            start_time_str = entity.get('execution_start_time')
                            if start_time_str:
                                try:
                                    start_time = datetime.fromisoformat(start_time_str)
                                    hours_old = (china_now - start_time).total_seconds() / 3600
                                    if hours_old > 2:
                                        update_job_execution_status(
                                            username, execution_id, 'failed',
                                            error_message=f"Job was running for {hours_old:.1f} hours, likely stuck"
                                        )
                                        logger.warning(f"Marked stuck job {execution_id} as failed")
                                        continue
                                except Exception as e:
                                    logger.warning(f"Error checking job age: {e}")
                        
                        # Execute missed jobs
                        try:
                            # Create job_config - all jobs run for all accounts, no account_names needed
                            job_config = {}
                            
                            # Update status to running
                            update_job_execution_status(username, execution_id, 'running')
                            
                            # Execute the job
                            executor_info = job_scheduler.executor_manager.executors.get(job_id)
                            if executor_info:
                                executor = executor_info[0]
                                logger.info(f"Executing missed job {job_id} for user {username}")
                                executor(username, job_config)
                                update_job_execution_status(username, execution_id, 'completed')
                                logger.info(f"Completed missed job {job_id} for user {username}")
                            else:
                                update_job_execution_status(
                                    username, execution_id, 'failed',
                                    error_message=f"Executor not found for job {job_id}"
                                )
                        except Exception as e:
                            logger.error(f"Error executing missed job {execution_id}: {e}")
                            update_job_execution_status(
                                username, execution_id, 'failed',
                                error_message=str(e)
                            )
                else:
                    logger.info("No missed jobs found")
            except Exception as e:
                logger.error(f"Error checking for missed jobs: {e}")
    else:
        logger.info(f"Job initialization and missed job execution disabled for {API_ENV} environment (local run)")
        
    # Only start scheduler thread in production environment
    if API_ENV == 'production':
        try:
            scheduler_thread = threading.Thread(target=scheduler_worker, daemon=True)
            scheduler_thread.start()
            logger.info("Job scheduler started in background thread")
        except Exception as e:
            logger.warning(f"Could not start job scheduler: {e}")
    else:
        logger.info(f"Job scheduler disabled for {API_ENV} environment (local run)")
        
    endpoints.set_globals(
        default_hall_setting=default_hall_setting,
        heroaccounts_table=heroaccounts_table,
        users_table=users_table,
        hall_combat_threads=hall_combat_threads,
        hall_combat_lock=hall_combat_lock,
        running_halls=running_halls,
        request_lock=request_lock,
        active_requests=active_requests,
        hall_stop_events=hall_stop_events,
        user_stop_signals=user_stop_signals,
        job_scheduler=job_scheduler,
        shutdown_requested=shutdown_requested,
        scheduler_paused=scheduler_paused,
        scheduler_paused_lock=scheduler_paused_lock,
        active_jobs=active_jobs,
        active_jobs_lock=active_jobs_lock
    )
    
    # Clean up any stale combat sessions from previous runs
    hall_utils.cleanup_stale_combat_sessions()
    
    # Purge old log files (older than 10 days)
    try:
        user_log_manager.purge_all_old_logs(days=10)
    except Exception as e:
        logger.warning(f"Failed to purge old logs: {e}")

    yield
    
    # Shutdown - wait for all active jobs to complete
    if scheduler_thread and scheduler_thread.is_alive():
        logger.info("Shutting down job scheduler...")
        # Wait for active jobs to complete
        import time
        max_wait_time = 1800  # 30 minutes max wait
        wait_start = time.time()
        
        while True:
            with active_jobs_lock:
                active_count = len(active_jobs)
            
            if active_count == 0:
                logger.info("All active jobs completed, shutdown complete")
                break
            
            elapsed = time.time() - wait_start
            if elapsed > max_wait_time:
                logger.warning(f"Shutdown timeout reached ({max_wait_time}s), {active_count} jobs still running")
                break
            
            logger.info(f"Waiting for {active_count} active jobs to complete... (elapsed: {elapsed:.0f}s)")
            time.sleep(5)  # Check every 5 seconds

app = FastAPI(
    docs_url="/docs" if SWAGGER_ENABLED else None,
    redoc_url="/redoc" if SWAGGER_ENABLED else None,
    openapi_url="/openapi.json" if SWAGGER_ENABLED else None,
    lifespan=lifespan
)

# Swagger status will be logged in lifespan event

# Allow frontend to call backend
# Get allowed origins from environment variable or use default
env_origins = os.getenv('ALLOWED_ORIGINS', '*')

if env_origins:
    # If the environment variable contains "*", use wildcard for all origins
    if '*' in env_origins:
        ALLOWED_ORIGINS = ["*"]
    else:
        # Otherwise, split by comma for specific origins
        ALLOWED_ORIGINS = env_origins.split(',')
else:
    ALLOWED_ORIGINS = ["*"]

logger.info(f"CORS allowed origins: {ALLOWED_ORIGINS}")

# Add CORS middleware first
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,  # Changed to False to avoid CORS issues with credentials
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"],
    max_age=86400,  # Cache preflight requests for 24 hours
)

# Custom middleware to log requests and errors
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logger.error(f"Request failed: {request.method} {request.url} - Error: {e}")
            raise

app.add_middleware(LoggingMiddleware)

# =============================================================================
# Azure Table Storage and Global Variables Setup
# =============================================================================

# Azure Table Storage setup
connection_string = os.getenv('connection_string')
if not connection_string:
    raise ValueError("connection_string environment variable is required")

table_service_client = TableServiceClient.from_connection_string(connection_string)
heroaccounts_table = table_service_client.get_table_client("heroaccounts")
users_table = table_service_client.get_table_client("herousers")


# Global variables for thread management and caching
hall_stop_events = {}
user_stop_signals = {}
active_requests = {}
request_lock = threading.Lock()
hall_combat_threads = {}
hall_combat_lock = threading.Lock()
running_halls = {}

# Default hall settings
default_hall_setting = {
    "封神异志": "",
    "平倭群英传": "跳过",
    "武林群侠传": "",
    "三国鼎立": "",
    "乱世群雄": "",
    "绝代风华": "",
    "复活重打": False,
    "客房补血": False,
    "自动买次数": False,
    "失败切换": True
}

# =============================================================================
# FastAPI Endpoints Registration
# =============================================================================

# Register all endpoints with the FastAPI app
app.get("/api/scheduler_status")(get_scheduler_status)
app.get("/api/health")(health_check)
# OPTIONS handlers removed - CORS middleware handles all preflight requests
app.post("/api/register")(register)
app.post("/api/login")(login)
app.post("/api/login/google")(login_with_google)
app.post("/api/refresh_token")(refresh_token)
app.get("/api/accounts")(get_accounts)
app.post("/api/accounts")(add_account)
app.post("/api/info")(get_info)
app.post("/api/duel_info")(get_duel_info)
app.post("/api/hall_combat_stream")(hall_combat_stream)
app.post("/api/hall_challenge")(hall_combat_stream)
app.post("/api/hall_challenge_multiple")(hall_combat_stream)
app.post("/api/resume_stream")(resume_stream)
app.get("/api/connection_status")(connection_status)
app.post("/api/clear_active_requests")(clear_active_requests)
app.post("/api/clear_stream_queue")(clear_stream_queue)
app.get("/api/log_files")(get_log_files)
app.get("/api/log_file_content")(get_log_file_content)
app.post("/api/stop_combat")(stop_combat)
app.delete("/api/accounts")(delete_account)
app.post("/api/refresh_cache")(refresh_cache)
app.post("/api/clear_cache")(clear_cache)
app.get("/api/cache_status")(cache_status)
app.get("/api/user_settings")(get_user_settings)
app.get("/api/jobs_table")(get_jobs_table)
app.get("/api/job_scheduler_status")(get_job_scheduler_status)
app.post("/api/set_job_settings")(set_job_settings)
app.get("/api/debug_user_settings")(debug_user_settings)
app.post("/api/buy_combat_count")(buy_combat_count)
app.post("/api/execute_job")(execute_job_manually)
app.post("/api/execute_command")(execute_command)
app.post("/api/olympics")(olympics)
app.post("/api/zongheng_challenge")(zongheng_challenge)
app.post("/api/lottery")(lottery)
app.post("/api/buy_duel_medal")(buy_duel_medal)
app.post("/api/get_fan_badges")(get_fan_badges)
app.post("/api/exchange_fan_badge")(exchange_fan_badge)
app.post("/api/auto_gift")(auto_gift)
app.post("/api/extract_cookies")(extract_cookies)
app.post("/api/extract_cookies_interactive")(extract_cookies_interactive)
app.post("/api/admin/open_browser_with_cookies")(open_browser_with_cookies)
app.get("/api/admin/players")(get_all_players)
app.get("/api/admin/players/{player_email}/accounts")(get_player_accounts)
app.post("/api/admin/players/{player_email}/toggle_status")(toggle_user_status)
app.get("/api/admin/job_status")(get_job_status)
app.post("/api/admin/shutdown")(initiate_shutdown)
app.get("/api/admin/shutdown_status")(get_shutdown_status)

# =============================================================================
# Jobs Configuration Management
# =============================================================================

def update_jobs_config(request: Request, data: dict = Body(...), current_user: str = Depends(verify_token)):
    """Update the jobs configuration"""
    try:
        new_config = data.get("jobs_config")
        if not new_config:
            raise HTTPException(status_code=400, detail="jobs_config is required")
        
        # Validate the configuration structure
        for job_id, job_config in new_config.items():
            if job_config["type"] not in ["daily", "hourly", "custom"]:
                raise HTTPException(status_code=400, detail=f"Job '{job_id}' has invalid type: {job_config['type']}")
        
        # Save to file
        if save_jobs_config(new_config, connection_string, current_user):
            # Update the global JOBS_TABLE
            return {
                "success": True,
                "message": "Jobs configuration updated successfully",
                "jobs_count": len(new_config)
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save jobs configuration")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update jobs configuration: {str(e)}")

app.post("/api/update_jobs_config")(update_jobs_config)

# =============================================================================
# Utility Modules Initialization
# =============================================================================

# Set table clients for utility modules
cache_utils.set_table_clients(heroaccounts_table, users_table)
auth_utils.set_user_table(users_table)
hall_utils.set_hall_globals(hall_combat_threads, hall_combat_lock, running_halls, hall_stop_events, user_stop_signals, default_hall_setting, users_table)
request_utils.set_request_globals(active_requests, request_lock)

# Global variables will be initialized in the lifespan startup event

# =============================================================================
# Application Entry Point
# =============================================================================

if __name__ == "__main__":
    logger.info(f'web server running')

    port = int(os.getenv('API_PORT') or 8080)
    reload = API_ENV == 'development'

    # All startup initialization moved to FastAPI startup event

    if os.getenv('ssl_certfile') and os.getenv('ssl_keyfile'):
        logger.info(f'SSL certfile: {os.getenv("ssl_certfile")}, SSL keyfile: {os.getenv("ssl_keyfile")}, uvicorn running on https://0.0.0.0:{port}')
        uvicorn.run("main:app", host="0.0.0.0", port=port, ssl_certfile=os.getenv('ssl_certfile'), ssl_keyfile=os.getenv('ssl_keyfile'), use_colors=False, reload=reload)
    else:
        if os.getenv('Nginx_SSL') == 'true':
            logger.info(f'uvicorn running on https://0.0.0.0:{port} with proxy headers')
            uvicorn.run("main:app", host="0.0.0.0", port=port, proxy_headers=True, forwarded_allow_ips="*", use_colors=False, reload=reload)
        else:
            logger.info(f'uvicorn running on http://0.0.0.0:{port}')
            uvicorn.run("main:app", host="0.0.0.0", port=port, use_colors=False, reload=reload)
        