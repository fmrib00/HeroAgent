"""
Job Scheduler Module

This module provides a flexible job scheduling system that supports different types of jobs:
- DAILY: Jobs that run once per day at a specific hour and minute (like auto_challenge)
- HOURLY: Jobs that run every hour at a specific minute (like cache refresh, health checks)
- CUSTOM: Jobs with custom schedules (can be extended for more complex patterns)

DATABASE INTEGRATION:
- Loads user settings and accounts directly from Azure Table Storage
- Always fetches fresh data from database for each job execution
- Uses Azure Table Service client for database operations

CONCURRENCY CONTROL:
- Uses ThreadPoolExecutor with bounded concurrency to prevent system overload
- Jobs are prioritized by schedule time (earlier schedules run first)
- Maximum concurrent workers can be configured via JOB_SCHEDULER_MAX_WORKERS environment variable
- Default: min(32, CPU_COUNT + 4) workers
"""

from typing import Callable, Any
import schedule
from azure.data.tables import TableServiceClient
import json, os, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import PriorityQueue
from log import setup_logging, get_user_logger, user_log_manager
from cache_utils import reset_all_combat_counts
from job_utils import capture_slave, morning_routines, night_routines, fengyun, wuguan
from job_utils import monday_routines, wednesday_routines, saturday_routines, dungeon_and_monster
from hall_utils import auto_challenge
from utils import get_china_now
from job_execution_tracker import (
    create_job_execution_record,
    update_job_execution_status,
    generate_execution_id
)

logger = setup_logging()

# These will be set by main.py after initialization
shutdown_requested = None
scheduler_paused = None
scheduler_paused_lock = None
active_jobs = None
active_jobs_lock = None

def set_shutdown_globals(shutdown_event, paused_flag, paused_lock, jobs_dict, jobs_lock):
    """Set global shutdown state variables from main.py"""
    global shutdown_requested, scheduler_paused, scheduler_paused_lock, active_jobs, active_jobs_lock
    shutdown_requested = shutdown_event
    scheduler_paused = paused_flag
    scheduler_paused_lock = paused_lock
    active_jobs = jobs_dict
    active_jobs_lock = jobs_lock
class JobType:
    """Job type constants"""
    DAILY = "daily"
    HOURLY = "hourly"
    WEEKLY = "weekly"
    CUSTOM = "custom"

def execute_auto_challenge_job(username: str, job_config: dict = None):
    """Execute auto challenge job for a user"""
    china_now = get_china_now()
    day_of_week = china_now.weekday()
    if day_of_week not in [3]:    # 跳过周二和周三和周四
        # Get account selection from job_config
        account_names = job_config.get('account_names', []) if job_config else []
        auto_challenge(username, account_names)

def execute_capture_slave_job(username: str, job_config: dict = None):
    """Execute capture slave job for a user"""
    # Get account selection from job_config
    account_names = job_config.get('account_names', []) if job_config else []
    capture_slave(username, account_names)

def execute_morning_routine_job(username: str, job_config: dict = None):
    """Execute arena job for a user"""
    # Get account selection from job_config
    account_names = job_config.get('account_names', []) if job_config else []
    morning_routines(username, account_names)

def execute_night_routine_job(username: str, job_config: dict = None):
    """Execute night routine job for a user"""
    # Get account selection from job_config
    account_names = job_config.get('account_names', []) if job_config else []
    night_routines(username, account_names)

def execute_monday_routine_job(username: str, job_config: dict = None):
    """Execute monday routine job for a user"""
    # Get account selection from job_config
    account_names = job_config.get('account_names', []) if job_config else []
    monday_routines(username, account_names)

def execute_fengyun_routine_job(username: str, job_config: dict = None):
    """Execute fengyun routine job for a user"""
    # Get account selection from job_config
    account_names = job_config.get('account_names', []) if job_config else []
    fengyun(username, account_names)

def execute_wednesday_routine_job(username: str, job_config: dict = None):
    """Execute wednesday routine job for a user"""
    # Get account selection from job_config
    account_names = job_config.get('account_names', []) if job_config else []
    wednesday_routines(username, account_names)
    reset_all_combat_counts(username)

def execute_saturday_routine_job(username: str, job_config: dict = None):
    """Execute saturday routine job for a user"""
    # Get account selection from job_config
    account_names = job_config.get('account_names', []) if job_config else []
    saturday_routines(username, account_names)

def execute_wuguan_routine_job(username: str, job_config: dict = None):
    """Execute wuguan routine job for a user"""
    # Get account selection from job_config
    account_names = job_config.get('account_names', []) if job_config else []
    wuguan(username, account_names)

def execute_dungeon_and_monster_routine_job(username: str, job_config: dict = None):
    """Execute dungeon routine job for a user"""
    # Get account selection from job_config
    account_names = job_config.get('account_names', []) if job_config else []
    dungeon_and_monster(username, account_names)

class ExecutorManager:
    """Manager for executing jobs"""
    def __init__(self):
        self.executors = {
            'auto_challenge': [execute_auto_challenge_job, "幻境挑战"],
            'capture_slave': [execute_capture_slave_job, "角色互奴"],
            'wuguan': [execute_wuguan_routine_job, "踢护武馆"],
            'morning_routine': [execute_morning_routine_job, "日常任务(早上)"],
            'night_routine': [execute_night_routine_job, "日常任务(晚上)"],
            'fengyun': [execute_fengyun_routine_job, "风云争霸"],
            'dungeon_and_monster': [execute_dungeon_and_monster_routine_job, "副本,打怪,渑池"],
            'monday_routine': [execute_monday_routine_job, "周一任务"],
            'wednesday_routine': [execute_wednesday_routine_job, "周三任务"],
            'saturday_routine': [execute_saturday_routine_job, "周六任务"],
        }
    
    def register_executor(self, executor_id: str, executor: Callable, executor_name: str):
        self.executors[executor_id] = [executor, executor_name]
    
    def get_executor(self, executor_id: str) -> Callable:
        executor_info = self.executors.get(executor_id)
        return executor_info[0] if executor_info else None
    
    def execute_job(self, executor_id: str, *args, **kwargs):
        executor_info = self.executors.get(executor_id)
        if executor_info:
            executor = executor_info[0]
            executor(*args, **kwargs)
        else:
            raise ValueError(f"Executor {executor_id} not found")

class JobScheduler:
    """Flexible job scheduler that supports different job types and schedules"""
    
    def __init__(self, connection_string: str, logger: Any):
        """
        Initialize the job scheduler with required dependencies
        
        Args:
            connection_string: Azure Table Storage connection string
            hall_combat_stream: Function to execute hall combat stream
            logger: Logger instance
            jobs_table: Jobs configuration table (optional)
        """
        self.connection_string = connection_string
        self.logger = logger
        
        # Initialize Azure Table Service client
        self.table_service_client = TableServiceClient.from_connection_string(connection_string)
        self.accounts_table = self.table_service_client.get_table_client("heroaccounts")
        self.user_settings_table = self.table_service_client.get_table_client("herousers")
        # Note: user_settings_table is actually the herousers table which contains user_type
        
        self.executor_manager = ExecutorManager()
        self.job_registry = {}
        # Track execution for daily/weekly jobs to prevent duplicate runs: (username, job_id, date) -> timestamp
        self.job_execution_tracker = {}
        self.tracker_lock = threading.Lock()
        # Thread pool configuration: limit concurrent user job processing to prevent system overload
        # Adjust max_workers based on your system capacity (CPU cores, database connections, etc.)
        # Default: min(32, (os.cpu_count() or 1) + 4) - reasonable default for most systems
        self.max_workers = int(os.getenv('JOB_SCHEDULER_MAX_WORKERS', min(32, (os.cpu_count() or 1) + 4)))
        self.setup_default_jobs()

    def available_jobs(self) -> dict:
        """Get all available jobs"""
        ret = {}
        for executor_id, executor in self.executor_manager.executors.items():
            ret[executor_id] = {
                'name': executor[1],
                'type': 'daily',
                'hour': '0',
                'minute': '0',
                'enabled': False,
                'executor': executor[0],
            }
        return ret
    
    def setup_default_jobs(self):
        """Register default job types"""
        self.job_registry[JobType.DAILY] = self.run_daily_jobs
        self.job_registry[JobType.HOURLY] = self.run_hourly_jobs
        self.job_registry[JobType.WEEKLY] = self.run_weekly_jobs
        self.logger.info(f"Registered jobs: {JobType.DAILY}, {JobType.HOURLY}, {JobType.WEEKLY}")
    
    def get_all_users_from_db(self) -> dict:
        """Get all usernames from both accounts and user_settings tables, excluding admin users"""
        user_settings = {}
        admin_users = set()  # Cache admin users to avoid repeated queries
        
        try:
            # Get usernames from user_settings table (herousers table)
            settings_entities = self.user_settings_table.list_entities()
            for entity in settings_entities:
                if 'PartitionKey' not in entity:
                    continue
                    
                username = entity['PartitionKey']
                
                # Skip if we already know this user is admin
                if username in admin_users:
                    continue
                
                # Check if user is admin - user_type is stored in entity with row_key='0'
                # First check if current entity has user_type
                user_type = entity.get('user_type', None)
                if user_type is None:
                    # Try to get the user entity with row_key='0' to check user_type
                    try:
                        user_entity = self.user_settings_table.get_entity(partition_key=username, row_key='0')
                        user_type = user_entity.get('user_type', 'player')
                    except Exception:
                        # If we can't check, assume it's a player (safer to include than exclude)
                        user_type = 'player'
                
                if user_type == 'admin':
                    # Skip admin users and cache the result
                    admin_users.add(username)
                    continue
                
                user_settings[username] = dict(entity)
        except Exception as e:
            self.logger.error(f"Error fetching user settings from user_settings table: {e}")
        
        return user_settings
    
    def _has_job_executed_today(self, username: str, job_id: str, china_now) -> bool:
        """Check if a daily/weekly job has already been executed today"""
        with self.tracker_lock:
            return (username, job_id, china_now.strftime('%Y-%m-%d')) in self.job_execution_tracker
    
    def _record_job_execution(self, username: str, job_id: str, china_now):
        """Record that a daily/weekly job has been executed"""
        with self.tracker_lock:
            self.job_execution_tracker[(username, job_id, china_now.strftime('%Y-%m-%d'))] = china_now
    
    def _process_user_jobs(self, username: str, user_settings: dict, job_type: str, china_now):
        """Process jobs for a single user (runs in a separate thread)"""
        try:
            # Check master job scheduling toggle first
            if not user_settings.get('job_scheduling_enabled', True):
                self.logger.info(f"Job scheduling is disabled for user {username}, skipping {job_type} jobs")
                return

            # self.logger.info(f"Starting {job_type} jobs for user {username}")
            # Parse job_settings if it exists
            job_settings = {}
            try:
                job_settings_str = user_settings.get("job_settings", "{}")
                job_settings = json.loads(job_settings_str) if job_settings_str else {}
            except (json.JSONDecodeError, TypeError):
                job_settings = {}
            
            user_logger = get_user_logger(username)

            # Check for enabled jobs (user scope only)
            jobs_executed = 0
            for job_id, job_config in job_settings.items():
                if job_config.get('type') == job_type and job_config.get('enabled', False):
                    should_run = False
                    
                    type_text = "每日" if job_type == JobType.DAILY else "每小时" if job_type == JobType.HOURLY else "每周"
                    if job_type == JobType.DAILY:
                        scheduled_hour = int(job_config.get('hour'))
                        scheduled_minute = int(job_config.get('minute', '0'))
                        # Allow job to run at scheduled minute or next minute (grace period for missed runs)
                        if china_now.hour == scheduled_hour and (china_now.minute == scheduled_minute or china_now.minute == scheduled_minute + 1):
                            should_run = True
                    elif job_type == JobType.HOURLY and china_now.minute == int(job_config.get('minute', '00')):
                        should_run = True
                    elif job_type == JobType.WEEKLY and china_now.weekday() == int(job_config.get('day_of_week')) and china_now.hour == int(job_config.get('hour')):
                        should_run = True
                    
                    if should_run:
                        # Check if daily/weekly job has already been executed to prevent duplicate runs
                        if (job_type == JobType.DAILY or job_type == JobType.WEEKLY) and self._has_job_executed_today(username, job_id, china_now):
                            self.logger.debug(f"Skipping {job_type} job '{job_id}' for user {username} - already executed")
                            continue
                        
                        try:
                            executor_info = self.executor_manager.executors.get(job_id)
                            if not executor_info:
                                self.logger.warning(f"No executor found for job '{job_id}'")
                                continue
                            executor = executor_info[0]
                            user_logger.info(f"开始执行 {type_text} 任务 {executor_info[1]}")
                            # Record execution for daily/weekly jobs
                            if job_type == JobType.DAILY or job_type == JobType.WEEKLY:
                                self._record_job_execution(username, job_id, china_now)
                            executor(username, job_config)
                            user_logger.info(f"执行 {type_text} 任务 {executor_info[1]} 完成")
                            jobs_executed += 1
                            self.logger.info(f"Executed {job_type} job '{job_id}' for user: {username} at {china_now}")
                        except Exception as e:
                            self.logger.error(f"Error executing job '{job_id}' for user {username}: {e}")
            
            # Log completion for this user
            # self.logger.info(f"{job_type} jobs completed for user {username}")
        except Exception as e:
            self.logger.error(f"Error processing {job_type} jobs for user {username}: {e}")

    def run_jobs(self, job_type: str):
        """
        Run all jobs for all users using a thread pool executor to prevent system overload.
        
        This method collects all jobs that need to run, prioritizes them by schedule time,
        and executes them using a bounded thread pool to limit concurrent execution.
        
        Args:
            job_type: Type of jobs to run (DAILY, HOURLY, WEEKLY)
        """
        # Check if shutdown is requested or scheduler is paused
        if shutdown_requested and shutdown_requested.is_set():
            self.logger.debug(f"Shutdown requested, skipping {job_type} jobs")
            return
        
        if scheduler_paused_lock:
            with scheduler_paused_lock:
                if scheduler_paused:
                    self.logger.debug(f"Scheduler paused, skipping {job_type} jobs")
                    return
        
        china_now = get_china_now()
        
        # self.logger.info(f"Starting {job_type} jobs at {china_now}")
        
        user_settings = self.get_all_users_from_db()
        
        # Collect all jobs that need to run with their priority (schedule time)
        # Priority queue format: (priority, counter, username, user_settings_data, job_id, job_config)
        # Counter ensures FIFO ordering for jobs with same priority
        job_queue = PriorityQueue()
        job_counter = 0
        
        for username, user_settings_data in user_settings.items():
            # Skip admin users - they don't have jobs
            user_type = user_settings_data.get('user_type', 'player')
            if user_type == 'admin':
                continue
            
            # Check master job scheduling toggle first
            if not user_settings_data.get('job_scheduling_enabled', True):
                continue
            
            # Parse job_settings
            try:
                job_settings_str = user_settings_data.get("job_settings", "{}")
                job_settings = json.loads(job_settings_str) if job_settings_str else {}
            except (json.JSONDecodeError, TypeError):
                job_settings = {}
            
            # Collect jobs for this user
            for job_id, job_config in job_settings.items():
                if job_config.get('type') == job_type and job_config.get('enabled', False):
                    should_run = False
                    priority = 0  # Lower number = higher priority (runs earlier)
                    
                    if job_type == JobType.DAILY:
                        scheduled_hour = int(job_config.get('hour'))
                        scheduled_minute = int(job_config.get('minute', '0'))
                        # Allow job to run at scheduled minute or next minute (grace period)
                        if china_now.hour == scheduled_hour and (china_now.minute == scheduled_minute or china_now.minute == scheduled_minute + 1):
                            should_run = True
                            # Priority: earlier scheduled times get lower priority numbers (run first)
                            # For same hour, earlier minutes get lower priority
                            priority = scheduled_hour * 60 + scheduled_minute
                    elif job_type == JobType.HOURLY and china_now.minute == int(job_config.get('minute', '00')):
                        should_run = True
                        # For hourly jobs, priority based on minute (earlier minutes run first)
                        priority = int(job_config.get('minute', '00'))
                    elif job_type == JobType.WEEKLY and china_now.weekday() == int(job_config.get('day_of_week')) and china_now.hour == int(job_config.get('hour')):
                        should_run = True
                        # For weekly jobs, priority based on day_of_week and hour
                        priority = int(job_config.get('day_of_week')) * 24 + int(job_config.get('hour'))
                    
                    if should_run:
                        # Check if daily/weekly job has already been executed
                        if (job_type == JobType.DAILY or job_type == JobType.WEEKLY) and self._has_job_executed_today(username, job_id, china_now):
                            self.logger.debug(f"Skipping {job_type} job '{job_id}' for user {username} - already executed")
                            continue
                        
                        # Create scheduled time for this job
                        scheduled_time = china_now.replace(second=0, microsecond=0)
                        if job_type == JobType.DAILY:
                            scheduled_time = scheduled_time.replace(
                                hour=int(job_config.get('hour')),
                                minute=int(job_config.get('minute', '0'))
                            )
                        elif job_type == JobType.HOURLY:
                            scheduled_time = scheduled_time.replace(
                                minute=int(job_config.get('minute', '00'))
                            )
                        elif job_type == JobType.WEEKLY:
                            scheduled_time = scheduled_time.replace(
                                hour=int(job_config.get('hour')),
                                minute=int(job_config.get('minute', '0'))
                            )
                        
                        # Check if execution record already exists, if not create it
                        execution_id = generate_execution_id(job_id, scheduled_time)
                        
                        # Try to get existing record
                        from job_execution_tracker import _job_executions_table
                        record_exists = False
                        if _job_executions_table:
                            try:
                                _job_executions_table.get_entity(partition_key=username, row_key=execution_id)
                                record_exists = True
                                # Record exists, use it
                            except Exception:
                                # Record doesn't exist, create it
                                # For hourly jobs, we create records on-demand (not pre-created)
                                execution_id = create_job_execution_record(
                                    username, job_id, job_type, scheduled_time
                                )
                                if not execution_id:
                                    execution_id = generate_execution_id(job_id, scheduled_time)
                        
                        if execution_id:
                            # Add to priority queue: (priority, counter, username, user_settings_data, job_id, job_config, execution_id)
                            job_queue.put((priority, job_counter, username, user_settings_data, job_id, job_config, execution_id))
                            job_counter += 1
                        else:
                            self.logger.warning(f"Failed to create/get execution record for job {job_id}, skipping")
        
        # Execute jobs using thread pool executor with bounded concurrency
        if job_queue.empty():
            return
        
        self.logger.info(f"Processing {job_queue.qsize()} {job_type} jobs with max {self.max_workers} concurrent workers")
        
        with ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix=f"{job_type}_job") as executor:
            futures = []
            
            # Submit jobs from priority queue to thread pool
            while not job_queue.empty():
                # Check shutdown again before submitting each job
                if shutdown_requested and shutdown_requested.is_set():
                    self.logger.info(f"Shutdown requested, stopping job submission for {job_type} jobs")
                    break
                
                priority, counter, username, user_settings_data, job_id, job_config, execution_id = job_queue.get()
                future = executor.submit(
                    self._execute_single_job,
                    username, user_settings_data, job_id, job_config, job_type, china_now, execution_id
                )
                futures.append(future)
            
            # Wait for all jobs to complete and handle any exceptions
            for future in as_completed(futures):
                try:
                    future.result()  # This will raise any exception that occurred
                except Exception as e:
                    # Exceptions are already logged in _execute_single_job
                    pass
    
    def _execute_single_job(self, username: str, user_settings_data: dict, job_id: str, job_config: dict, job_type: str, china_now, execution_id: str):
        """
        Execute a single job for a user. This runs in a thread pool worker.
        
        Args:
            username: Username
            user_settings_data: User settings dictionary
            job_id: Job ID
            job_config: Job configuration
            job_type: Type of job (DAILY, HOURLY, WEEKLY)
            china_now: Current China time
            execution_id: Execution ID for tracking
        """
        import time
        start_time = time.time()
        
        try:
            # Update status to running and add to active jobs
            update_job_execution_status(username, execution_id, 'running')
            
            if active_jobs_lock and active_jobs is not None:
                with active_jobs_lock:
                    active_jobs[execution_id] = {
                        'username': username,
                        'job_id': job_id,
                        'start_time': start_time,
                        'future': None  # Will be set by caller if needed
                    }
            
            user_logger = get_user_logger(username)
            
            executor_info = self.executor_manager.executors.get(job_id)
            if not executor_info:
                self.logger.warning(f"No executor found for job '{job_id}'")
                update_job_execution_status(
                    username, execution_id, 'failed',
                    error_message=f"Executor not found for job {job_id}"
                )
                return
            
            executor = executor_info[0]
            type_text = "每日" if job_type == JobType.DAILY else "每小时" if job_type == JobType.HOURLY else "每周"
            
            user_logger.info(f"开始执行 {type_text} 任务 {executor_info[1]}")
            
            # Record execution for daily/weekly jobs before execution to prevent duplicates
            if job_type == JobType.DAILY or job_type == JobType.WEEKLY:
                self._record_job_execution(username, job_id, china_now)
            
            executor(username, job_config)
            user_logger.info(f"执行 {type_text} 任务 {executor_info[1]} 完成")
            self.logger.info(f"Executed {job_type} job '{job_id}' for user: {username} at {china_now}")
            
            # Update status to completed
            update_job_execution_status(username, execution_id, 'completed')
            
            # For hourly jobs, create the next scheduled record after completion
            if job_type == JobType.HOURLY:
                from datetime import timedelta
                from job_execution_tracker import create_job_execution_record
                # Calculate next hour's scheduled time
                scheduled_minute = int(job_config.get('minute', '00'))
                next_hour = china_now.hour + 1
                if next_hour >= 24:
                    # Next day
                    next_scheduled_time = (china_now + timedelta(days=1)).replace(
                        hour=0,
                        minute=scheduled_minute,
                        second=0,
                        microsecond=0
                    )
                else:
                    next_scheduled_time = china_now.replace(
                        hour=next_hour,
                        minute=scheduled_minute,
                        second=0,
                        microsecond=0
                    )
                # Create record for next hourly job
                create_job_execution_record(
                    username, job_id, job_type, next_scheduled_time
                )
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Error executing job '{job_id}' for user {username}: {e}", exc_info=True)
            update_job_execution_status(username, execution_id, 'failed', error_message=error_msg)
        finally:
            # Remove from active jobs
            if active_jobs_lock and active_jobs is not None:
                with active_jobs_lock:
                    active_jobs.pop(execution_id, None)

    def run_daily_jobs(self):
        """Run all daily jobs for all users using database data and jobs table"""
        self.run_jobs(JobType.DAILY)

    def run_hourly_jobs(self):
        """Run all hourly jobs for all users using database data and jobs table"""
        self.run_jobs(JobType.HOURLY)
    
    def run_weekly_jobs(self):
        """Run all weekly jobs for all users using database data and jobs table"""
        self.run_jobs(JobType.WEEKLY)
    
    def run_job_type(self, job_type: str):
        """Run jobs of a specific type"""
        if job_type in self.job_registry:
            self.job_registry[job_type]()
        else:
            self.logger.warning(f"Unknown job type: {job_type}")

def purge_old_logs_job():
    """Job to purge old log files"""
    try:
        logger.info("Running scheduled log purge job")
        user_log_manager.purge_all_old_logs(days=10)
    except Exception as e:
        logger.error(f"Error in scheduled log purge job: {e}")

def initialize_daily_job_records_job():
    """Job to initialize daily job execution records at the start of each day"""
    try:
        from job_execution_tracker import initialize_daily_job_records, cleanup_old_job_records
        from utils import get_china_now
        
        china_now = get_china_now()
        logger.info("Running daily job records initialization (start of new day)")
        
        # Always clean up old records and initialize for today
        # This ensures we only keep today's records
        cleanup_old_job_records(china_now.replace(hour=0, minute=0, second=0, microsecond=0))
        
        # Get job_scheduler from global scope (set in main.py)
        import sys
        main_module = sys.modules.get('main')
        if main_module and hasattr(main_module, 'job_scheduler') and main_module.job_scheduler:
            initialize_daily_job_records(main_module.job_scheduler, china_now)
        else:
            logger.warning("Job scheduler not available for daily initialization")
    except Exception as e:
        logger.error(f"Error in daily job records initialization job: {e}", exc_info=True)

def setup_scheduler_jobs(scheduler: JobScheduler):
    """Set up the scheduler for all job types"""
    logger = scheduler.logger
    
    API_ENV = os.getenv('API_ENV') or 'development'
    if API_ENV != 'production':
        logger.info(f"Job scheduling is disabled for development environment, skipping all jobs")
        return

    # Clear any existing jobs to prevent duplicates
    schedule.clear()
    logger.info("Cleared existing scheduled jobs")
    
    schedule.every().minutes.do(lambda: threading.Thread(target=scheduler.run_hourly_jobs, daemon=True).start())
    logger.info("Scheduled hourly jobs to run every minute (async dispatch, minute-specific support)")
    
    schedule.every().minutes.do(lambda: threading.Thread(target=scheduler.run_daily_jobs, daemon=True).start())
    logger.info("Scheduled daily jobs to run every minute (async dispatch, hour and minute-specific support)")
    
    # Schedule log purge to run daily at 3 AM China time
    schedule.every().day.at("03:00").do(purge_old_logs_job)
    logger.info("Scheduled log purge job to run daily at 3:00 AM China time")
    
    schedule.every().hour.at(":00").do(scheduler.run_weekly_jobs)
    logger.info("Scheduled weekly jobs to run at exact hour boundaries")
    
    # Schedule daily job records initialization to run at 00:00 (start of each day)
    schedule.every().day.at("00:00").do(initialize_daily_job_records_job)
    logger.info("Scheduled daily job records initialization to run at 00:00")

def scheduler_worker():
    """Background worker that runs the scheduler"""
    import time
    from log import setup_logging
    logger = setup_logging()
    try:
        while True:
            # Check if shutdown is requested
            if shutdown_requested and shutdown_requested.is_set():
                logger.info("Shutdown requested, stopping scheduler worker")
                break
            
            # Check if scheduler is paused
            if scheduler_paused_lock:
                with scheduler_paused_lock:
                    if scheduler_paused:
                        logger.debug("Scheduler paused, skipping this cycle")
                        time.sleep(60)
                        continue
            
            # Use the schedule library to check for pending jobs
            # This is much cleaner and doesn't require hardcoding times
            schedule.run_pending()
            time.sleep(60)  # Check every 60 seconds for responsiveness
    except KeyboardInterrupt:
        logger.info("Scheduler worker stopped")
    except Exception as e:
        logger.error(f"Scheduler worker error: {e}")