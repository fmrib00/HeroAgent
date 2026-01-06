"""
Job Execution Tracker Module

This module handles persistence of job execution state to Azure Table Storage.
Tracks job execution status to enable graceful shutdown and recovery of missed jobs.
"""

from datetime import datetime
from typing import Optional, Dict, List
from azure.data.tables import TableClient
import json
import threading
from log import setup_logging
from utils import get_china_now

logger = setup_logging()

# Global table client - will be set during initialization
_job_executions_table: Optional[TableClient] = None
_table_lock = threading.Lock()


def initialize_job_executions_table(connection_string: str):
    """Initialize the job executions table client"""
    global _job_executions_table
    from azure.data.tables import TableServiceClient
    
    with _table_lock:
        if _job_executions_table is None:
            table_service_client = TableServiceClient.from_connection_string(connection_string)
            _job_executions_table = table_service_client.get_table_client("herojobexecutions")
            # Ensure table exists
            try:
                _job_executions_table.create_table()
                logger.info("Created herojobexecutions table")
            except Exception as e:
                # Table might already exist, which is fine
                if "TableAlreadyExists" not in str(e):
                    logger.warning(f"Could not create herojobexecutions table: {e}")


def generate_execution_id(job_id: str, scheduled_time: datetime) -> str:
    """Generate a unique execution ID for a job"""
    # Format: {job_id}_{YYYY-MM-DD}_{HH:MM:SS}
    date_str = scheduled_time.strftime('%Y-%m-%d')
    time_str = scheduled_time.strftime('%H:%M:%S')
    return f"{job_id}_{date_str}_{time_str}"


def create_job_execution_record(
    username: str,
    job_id: str,
    job_type: str,
    scheduled_time: datetime
) -> str:
    """
    Create a new job execution record in the database.
    All jobs are run for all game accounts, so account_names is not stored.
    
    Returns:
        execution_id: The unique execution ID
    """
    global _job_executions_table
    
    if _job_executions_table is None:
        logger.error("Job executions table not initialized")
        return None
    
    execution_id = generate_execution_id(job_id, scheduled_time)
    
    entity = {
        'PartitionKey': username,
        'RowKey': execution_id,
        'job_id': job_id,
        'job_type': job_type,
        'scheduled_time': scheduled_time.isoformat(),
        'execution_start_time': None,
        'execution_end_time': None,
        'status': 'pending',
        'error_message': None
    }
    
    try:
        _job_executions_table.upsert_entity(entity)
        logger.debug(f"Created job execution record: {execution_id} for user {username}")
        return execution_id
    except Exception as e:
        logger.error(f"Failed to create job execution record: {e}")
        return None


def update_job_execution_status(
    username: str,
    execution_id: str,
    status: str,
    error_message: Optional[str] = None
):
    """
    Update the status of a job execution record.
    
    Args:
        username: Username (PartitionKey)
        execution_id: Execution ID (RowKey)
        status: New status ('pending', 'running', 'completed', 'failed', 'missed')
        error_message: Optional error message if status is 'failed'
    """
    global _job_executions_table
    
    if _job_executions_table is None:
        logger.error("Job executions table not initialized")
        return
    
    try:
        # Get existing entity
        entity = _job_executions_table.get_entity(partition_key=username, row_key=execution_id)
        
        # Update fields
        entity['status'] = status
        
        if status == 'running':
            if entity.get('execution_start_time') is None:
                entity['execution_start_time'] = get_china_now().isoformat()
        elif status in ('completed', 'failed'):
            entity['execution_end_time'] = get_china_now().isoformat()
            if error_message:
                entity['error_message'] = error_message
        
        _job_executions_table.update_entity(entity)
        logger.debug(f"Updated job execution {execution_id} status to {status}")
    except Exception as e:
        logger.error(f"Failed to update job execution status: {e}")


def get_missed_jobs() -> List[Dict]:
    """
    Get all jobs that were scheduled to run but haven't completed.
    Returns jobs with status 'pending' or 'running' where scheduled_time < now()
    
    Returns:
        List of job execution entities
    """
    global _job_executions_table
    
    if _job_executions_table is None:
        logger.error("Job executions table not initialized")
        return []
    
    try:
        china_now = get_china_now()
        missed_jobs = []
        
        # Query for pending or running jobs
        filter_query = "status eq 'pending' or status eq 'running'"
        entities = _job_executions_table.query_entities(query_filter=filter_query)
        
        for entity in entities:
            scheduled_time_str = entity.get('scheduled_time')
            if scheduled_time_str:
                scheduled_time = datetime.fromisoformat(scheduled_time_str)
                if scheduled_time < china_now:
                    missed_jobs.append(entity)
        
        return missed_jobs
    except Exception as e:
        logger.error(f"Failed to get missed jobs: {e}")
        return []


def get_active_jobs_from_db() -> List[Dict]:
    """
    Get all currently running jobs from the database.
    
    Returns:
        List of job execution entities with status 'running'
    """
    global _job_executions_table
    
    if _job_executions_table is None:
        logger.error("Job executions table not initialized")
        return []
    
    try:
        filter_query = "status eq 'running'"
        entities = _job_executions_table.query_entities(query_filter=filter_query)
        return list(entities)
    except Exception as e:
        logger.error(f"Failed to get active jobs from DB: {e}")
        return []


def get_recent_executions(username: Optional[str] = None, limit: int = 50) -> List[Dict]:
    """
    Get recent job executions, optionally filtered by username.
    
    Args:
        username: Optional username to filter by
        limit: Maximum number of records to return
    
    Returns:
        List of recent job execution entities
    """
    global _job_executions_table
    
    if _job_executions_table is None:
        logger.error("Job executions table not initialized")
        return []
    
    try:
        if username:
            # Query for specific user
            entities = _job_executions_table.query_entities(
                query_filter=f"PartitionKey eq '{username}'"
            )
        else:
            # Query all entities (limited)
            entities = _job_executions_table.list_entities()
        
        # Convert to list and sort by scheduled_time descending
        executions = list(entities)
        executions.sort(
            key=lambda x: x.get('scheduled_time', ''),
            reverse=True
        )
        
        return executions[:limit]
    except Exception as e:
        logger.error(f"Failed to get recent executions: {e}")
        return []


def cleanup_old_job_records(before_date: datetime = None):
    """
    Clean up job execution records older than the specified date.
    If before_date is None, cleans up all records before today.
    
    Args:
        before_date: Date before which records should be deleted (defaults to today)
    """
    global _job_executions_table
    
    if _job_executions_table is None:
        logger.error("Job executions table not initialized")
        return
    
    if before_date is None:
        before_date = get_china_now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    try:
        logger.info(f"Cleaning up job execution records before {before_date.strftime('%Y-%m-%d')}")
        deleted_count = 0
        
        # Query for all records with scheduled_time before the specified date
        filter_query = f"scheduled_time lt '{before_date.isoformat()}'"
        entities = _job_executions_table.query_entities(query_filter=filter_query)
        
        for entity in entities:
            try:
                _job_executions_table.delete_entity(
                    partition_key=entity['PartitionKey'],
                    row_key=entity['RowKey']
                )
                deleted_count += 1
            except Exception as e:
                logger.warning(f"Failed to delete record {entity.get('RowKey')}: {e}")
        
        logger.info(f"Cleaned up {deleted_count} old job execution records")
    except Exception as e:
        logger.error(f"Failed to cleanup old job records: {e}", exc_info=True)


def get_daily_job_summary(target_date: datetime = None) -> Dict:
    """
    Get a summary of all job executions for a specific date.
    
    Args:
        target_date: Date to summarize (defaults to today)
    
    Returns:
        Dictionary with summary statistics
    """
    global _job_executions_table
    
    if _job_executions_table is None:
        logger.error("Job executions table not initialized")
        return {}
    
    if target_date is None:
        target_date = get_china_now()
    
    try:
        from datetime import timedelta
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        
        # Query for records with scheduled_time on this date
        filter_query = f"scheduled_time ge '{start_of_day.isoformat()}' and scheduled_time lt '{end_of_day.isoformat()}'"
        entities = _job_executions_table.query_entities(query_filter=filter_query)
        
        summary = {
            'date': start_of_day.strftime('%Y-%m-%d'),
            'total': 0,
            'pending': 0,
            'running': 0,
            'completed': 0,
            'failed': 0,
            'missed': 0,
            'jobs_by_status': {},
            'jobs_by_user': {},
            'jobs': []
        }
        
        for entity in entities:
            summary['total'] += 1
            status = entity.get('status', 'unknown')
            
            if status == 'pending':
                summary['pending'] += 1
            elif status == 'running':
                summary['running'] += 1
            elif status == 'completed':
                summary['completed'] += 1
            elif status == 'failed':
                summary['failed'] += 1
            elif status == 'missed':
                summary['missed'] += 1
            
            # Count by status
            if status not in summary['jobs_by_status']:
                summary['jobs_by_status'][status] = 0
            summary['jobs_by_status'][status] += 1
            
            # Count by user
            username = entity.get('PartitionKey', 'unknown')
            if username not in summary['jobs_by_user']:
                summary['jobs_by_user'][username] = {
                    'total': 0,
                    'completed': 0,
                    'failed': 0,
                    'pending': 0,
                    'running': 0
                }
            summary['jobs_by_user'][username]['total'] += 1
            if status in summary['jobs_by_user'][username]:
                summary['jobs_by_user'][username][status] += 1
            
            # Store job details
            job_info = {
                'username': username,
                'job_id': entity.get('job_id'),
                'job_type': entity.get('job_type'),
                'status': status,
                'scheduled_time': entity.get('scheduled_time'),
                'execution_start_time': entity.get('execution_start_time'),
                'execution_end_time': entity.get('execution_end_time'),
                'error_message': entity.get('error_message')
            }
            summary['jobs'].append(job_info)
        
        # Sort jobs by scheduled_time
        summary['jobs'].sort(key=lambda x: x.get('scheduled_time', ''))
        
        return summary
    except Exception as e:
        logger.error(f"Failed to get daily job summary: {e}", exc_info=True)
        return {}


def print_daily_job_summary(target_date: datetime = None):
    """
    Print a formatted summary of job executions for a specific date.
    
    Args:
        target_date: Date to summarize (defaults to today)
    """
    summary = get_daily_job_summary(target_date)
    
    if not summary or summary['total'] == 0:
        logger.info("=" * 80)
        logger.info("DAILY JOB SUMMARY - No job records found for today")
        logger.info("=" * 80)
        return
    
    date_str = summary['date']
    logger.info("=" * 80)
    logger.info(f"DAILY JOB SUMMARY - {date_str}")
    logger.info("=" * 80)
    logger.info(f"Total Jobs: {summary['total']}")
    logger.info(f"  - Completed: {summary['completed']}")
    logger.info(f"  - Failed: {summary['failed']}")
    logger.info(f"  - Pending: {summary['pending']}")
    logger.info(f"  - Running: {summary['running']}")
    logger.info(f"  - Missed: {summary['missed']}")
    logger.info("")
    
    # Summary by user
    if summary['jobs_by_user']:
        logger.info("Summary by User:")
        for username, stats in sorted(summary['jobs_by_user'].items()):
            logger.info(f"  {username}:")
            logger.info(f"    Total: {stats['total']}, Completed: {stats['completed']}, "
                       f"Failed: {stats['failed']}, Pending: {stats['pending']}, Running: {stats['running']}")
        logger.info("")
    
    # List all jobs with details
    logger.info("Job Details:")
    for job in summary['jobs']:
        scheduled_time = job.get('scheduled_time', 'N/A')
        start_time = job.get('execution_start_time', 'N/A')
        end_time = job.get('execution_end_time', 'N/A')
        status = job.get('status', 'unknown')
        job_id = job.get('job_id', 'N/A')
        username = job.get('username', 'N/A')
        job_type = job.get('job_type', 'N/A')
        
        status_symbol = {
            'completed': '✓',
            'failed': '✗',
            'pending': '○',
            'running': '▶',
            'missed': '⚠'
        }.get(status, '?')
        
        logger.info(f"  {status_symbol} [{username}] {job_id} ({job_type}) - Status: {status}")
        logger.info(f"      Scheduled: {scheduled_time}")
        if start_time != 'N/A':
            logger.info(f"      Started: {start_time}")
        if end_time != 'N/A':
            logger.info(f"      Ended: {end_time}")
        if job.get('error_message'):
            logger.info(f"      Error: {job['error_message']}")
    
    logger.info("=" * 80)


def check_job_records_exist_for_date(target_date: datetime) -> bool:
    """
    Check if any job execution records exist for a specific date.
    
    Args:
        target_date: Date to check (datetime object)
    
    Returns:
        True if records exist for this date, False otherwise
    """
    global _job_executions_table
    
    if _job_executions_table is None:
        logger.error("Job executions table not initialized")
        return False
    
    try:
        # Use scheduled_time to check - more efficient than checking RowKey
        from datetime import timedelta
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        
        # Query for records with scheduled_time between start and end of day
        filter_query = f"scheduled_time ge '{start_of_day.isoformat()}' and scheduled_time lt '{end_of_day.isoformat()}'"
        entities = _job_executions_table.query_entities(query_filter=filter_query)
        
        # Check if any entities exist
        try:
            first_entity = next(entities)
            return True
        except StopIteration:
            return False
    except Exception as e:
        logger.error(f"Failed to check job records for date: {e}")
        return False


def initialize_daily_job_records(job_scheduler, target_date: datetime = None):
    """
    Initialize job execution records for all scheduled jobs for a given date.
    If target_date is None, uses today's date.
    
    This function:
    1. Cleans up old records (before today)
    2. Creates 'pending' records for all scheduled jobs that haven't run yet
    3. Marks jobs that should have already run as 'completed' (assuming they ran successfully)
    
    Args:
        job_scheduler: JobScheduler instance
        target_date: Date to initialize records for (defaults to today)
    """
    global _job_executions_table
    
    if _job_executions_table is None:
        logger.error("Job executions table not initialized")
        return
    
    china_now = get_china_now()
    if target_date is None:
        target_date = china_now
    
    target_date_str = target_date.strftime('%Y-%m-%d')
    logger.info(f"Initializing job execution records for date: {target_date_str}")
    
    # First, clean up old records (before today)
    cleanup_old_job_records(target_date.replace(hour=0, minute=0, second=0, microsecond=0))
    
    # Import timedelta for hourly job calculation
    from datetime import timedelta
    
    try:
        user_settings = job_scheduler.get_all_users_from_db()
        records_created = 0
        records_completed = 0
        
        for username, user_settings_data in user_settings.items():
            # Skip admin users - they don't have jobs
            user_type = user_settings_data.get('user_type', 'player')
            if user_type == 'admin':
                continue
            
            # Check master job scheduling toggle
            if not user_settings_data.get('job_scheduling_enabled', True):
                continue
            
            # Parse job_settings
            try:
                job_settings_str = user_settings_data.get("job_settings", "{}")
                job_settings = json.loads(job_settings_str) if job_settings_str else {}
            except (json.JSONDecodeError, TypeError):
                job_settings = {}
            
            # Process each job type
            for job_id, job_config in job_settings.items():
                if not job_config.get('enabled', False):
                    continue
                
                job_type = job_config.get('type')
                
                if job_type == 'daily':
                    # Create record for daily job
                    scheduled_hour = int(job_config.get('hour', 0))
                    scheduled_minute = int(job_config.get('minute', 0))
                    scheduled_time = target_date.replace(
                        hour=scheduled_hour,
                        minute=scheduled_minute,
                        second=0,
                        microsecond=0
                    )
                    
                    execution_id = generate_execution_id(job_id, scheduled_time)
                    
                    # Check if record already exists
                    try:
                        _job_executions_table.get_entity(partition_key=username, row_key=execution_id)
                        # Record exists, skip
                        continue
                    except Exception:
                        # Record doesn't exist, create it
                        pass
                    
                    # Determine status: if scheduled_time < now, mark as completed (assumed successful)
                    if scheduled_time < china_now:
                        status = 'completed'
                        execution_start_time = scheduled_time.isoformat()
                        execution_end_time = scheduled_time.isoformat()
                        records_completed += 1
                    else:
                        status = 'pending'
                        execution_start_time = None
                        execution_end_time = None
                        records_created += 1
                    
                    entity = {
                        'PartitionKey': username,
                        'RowKey': execution_id,
                        'job_id': job_id,
                        'job_type': job_type,
                        'scheduled_time': scheduled_time.isoformat(),
                        'execution_start_time': execution_start_time,
                        'execution_end_time': execution_end_time,
                        'status': status,
                        'error_message': None
                    }
                    
                    _job_executions_table.upsert_entity(entity)
                    
                elif job_type == 'hourly':
                    # For hourly jobs, only create the next scheduled record (not all 24 hours)
                    scheduled_minute = int(job_config.get('minute', 0))
                    
                    # Calculate next scheduled time
                    current_hour = china_now.hour
                    current_minute = china_now.minute
                    
                    # If current minute is past the scheduled minute, schedule for next hour
                    if current_minute >= scheduled_minute:
                        next_hour = current_hour + 1
                        if next_hour >= 24:
                            # If past midnight, schedule for tomorrow
                            next_scheduled_time = (target_date + timedelta(days=1)).replace(
                                hour=0,
                                minute=scheduled_minute,
                                second=0,
                                microsecond=0
                            )
                        else:
                            next_scheduled_time = target_date.replace(
                                hour=next_hour,
                                minute=scheduled_minute,
                                second=0,
                                microsecond=0
                            )
                    else:
                        # Current hour hasn't reached scheduled minute yet, schedule for this hour
                        next_scheduled_time = target_date.replace(
                            hour=current_hour,
                            minute=scheduled_minute,
                            second=0,
                            microsecond=0
                        )
                    
                    execution_id = generate_execution_id(job_id, next_scheduled_time)
                    
                    # Check if record already exists
                    try:
                        _job_executions_table.get_entity(partition_key=username, row_key=execution_id)
                        # Record exists, skip
                        continue
                    except Exception:
                        # Record doesn't exist, create it
                        pass
                    
                    # Next scheduled job is always pending
                    status = 'pending'
                    execution_start_time = None
                    execution_end_time = None
                    records_created += 1
                    
                    entity = {
                        'PartitionKey': username,
                        'RowKey': execution_id,
                        'job_id': job_id,
                        'job_type': job_type,
                        'scheduled_time': next_scheduled_time.isoformat(),
                        'execution_start_time': execution_start_time,
                        'execution_end_time': execution_end_time,
                        'status': status,
                        'error_message': None
                    }
                    
                    _job_executions_table.upsert_entity(entity)
                        
                elif job_type == 'weekly':
                    # Create record for weekly job if it's the scheduled day
                    day_of_week = int(job_config.get('day_of_week', 0))
                    scheduled_hour = int(job_config.get('hour', 0))
                    scheduled_minute = int(job_config.get('minute', 0))
                    
                    if target_date.weekday() == day_of_week:
                        scheduled_time = target_date.replace(
                            hour=scheduled_hour,
                            minute=scheduled_minute,
                            second=0,
                            microsecond=0
                        )
                        
                        execution_id = generate_execution_id(job_id, scheduled_time)
                        
                        # Check if record already exists
                        try:
                            _job_executions_table.get_entity(partition_key=username, row_key=execution_id)
                            continue
                        except Exception:
                            pass
                        
                        # Determine status
                        if scheduled_time < china_now:
                            status = 'completed'
                            execution_start_time = scheduled_time.isoformat()
                            execution_end_time = scheduled_time.isoformat()
                            records_completed += 1
                        else:
                            status = 'pending'
                            execution_start_time = None
                            execution_end_time = None
                            records_created += 1
                        
                        entity = {
                            'PartitionKey': username,
                            'RowKey': execution_id,
                            'job_id': job_id,
                            'job_type': job_type,
                            'scheduled_time': scheduled_time.isoformat(),
                            'execution_start_time': execution_start_time,
                            'execution_end_time': execution_end_time,
                            'status': status,
                            'error_message': None
                        }
                        
                        _job_executions_table.upsert_entity(entity)
        
        logger.info(f"Initialized job records for {target_date_str}: {records_created} pending, {records_completed} completed (assumed successful)")
    except Exception as e:
        logger.error(f"Failed to initialize daily job records: {e}", exc_info=True)
