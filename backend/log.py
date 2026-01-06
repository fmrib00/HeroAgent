import logging
import logging.handlers
import queue
import os
import re
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict

# China timezone (UTC+8)
CHINA_TZ = timezone(timedelta(hours=8))

class ChinaTimeFormatter(logging.Formatter):
    """Custom formatter that always uses China timezone"""
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=CHINA_TZ)
        if datefmt:
            return dt.strftime(datefmt)
        else:
            return dt.strftime('%Y-%m-%d %H:%M:%S')

# Global logger for system-level logs
system_logger = logging.getLogger('herohall_system')

logging.getLogger('azure').setLevel(logging.WARNING)
logging.getLogger('azure.core').setLevel(logging.WARNING)
logging.getLogger('azure.storage').setLevel(logging.WARNING)
logging.getLogger('azure.data.tables').setLevel(logging.WARNING)
logging.getLogger('azure.storage.blob').setLevel(logging.WARNING)

class UserStreamingLogHandler(logging.Handler):
    """Streaming log handler for real-time frontend updates"""
    def __init__(self, username: str):
        super().__init__()
        self.username = username
        self.log_queue = queue.Queue()

    def emit(self, record):
        msg = self.format(record)
        self.log_queue.put(msg)

class UserFileLogHandler(logging.Handler):
    """File log handler for persistent storage with daily rotation"""
    def __init__(self, username: str, log_dir: str):
        super().__init__()
        self.username = username
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.current_log_file = None
        self._file_handle = None
        self._lock = threading.Lock()
        self.current_date = None  # Track which day the current log is for

    def _should_rotate(self):
        """Check if we should rotate to a new log file (new day)"""
        now = datetime.now(tz=CHINA_TZ)
        today = now.date()
        
        # Rotate if we don't have a file yet or if the date has changed
        if self.current_date is None or self.current_date != today:
            return True
        return False

    def _create_new_log_file(self):
        """Create a new log file for today"""
        now = datetime.now(tz=CHINA_TZ)
        self.current_date = now.date()
        
        # Use date-based naming: YYYY-MM-DD.log
        date_str = now.strftime("%Y-%m-%d")
        self.current_log_file = self.log_dir / f"{date_str}.log"
        
        # Close existing handle if any
        if self._file_handle:
            try:
                self._file_handle.close()
            except Exception as e:
                system_logger.error(f"Error closing previous log file handle: {e}")
        
        # Open new file handle
        try:
            self._file_handle = open(self.current_log_file, 'a', encoding='utf-8')
            system_logger.info(f"Created new log file for {self.username}: {self.current_log_file}")
        except Exception as e:
            system_logger.error(f"Failed to open log file {self.current_log_file}: {e}")
            self._file_handle = None

    def emit(self, record):
        with self._lock:
            # Check if we need to rotate to a new day's log file
            if self._should_rotate():
                self._create_new_log_file()
            
            msg = self.format(record)
            try:
                if self._file_handle:
                    self._file_handle.write(msg + '\n')
                    self._file_handle.flush()  # Ensure data is written immediately
            except Exception as e:
                system_logger.error(f"Failed to write to log file {self.current_log_file}: {e}")

    def rotate_log(self):
        """Rotate to a new log file"""
        with self._lock:
            if self._file_handle:
                try:
                    self._file_handle.close()
                except Exception as e:
                    system_logger.error(f"Error closing log file handle: {e}")
                self._file_handle = None
            self.current_log_file = None
            self.current_date = None  # Reset date to force rotation on next emit

    def close(self):
        """Close the file handle when handler is destroyed"""
        with self._lock:
            if self._file_handle:
                try:
                    self._file_handle.close()
                except Exception as e:
                    system_logger.error(f"Error closing log file handle: {e}")
                self._file_handle = None
        super().close()

class UserLogManager:
    """Manages per-user logging with file persistence and real-time streaming"""
    
    def __init__(self):
        self.user_loggers: Dict[str, logging.Logger] = {}
        self.user_handlers: Dict[str, Dict] = {}
        self._lock = threading.Lock()
        
        # Create logs directory
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)
        
        # Setup system logger
        self._setup_system_logger()

    def _setup_system_logger(self):
        """Setup system-level logger"""
        system_logger.setLevel(logging.INFO)
        
        # Console handler for system logs
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(ChinaTimeFormatter(
            '%(asctime)s [SYSTEM] %(message)s', 
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        system_logger.addHandler(console_handler)
        
        # File handler for system logs with daily rotation and 30-day retention
        # backupCount=29 means: current file (today) + 29 backup files = 30 days total
        system_log_path = self.logs_dir / "system.log"
        system_file_handler = logging.handlers.TimedRotatingFileHandler(
            system_log_path,
            when='midnight',
            interval=1,
            backupCount=29,
            encoding='utf-8'
        )
        system_file_handler.setLevel(logging.INFO)
        system_file_handler.setFormatter(ChinaTimeFormatter(
            '%(asctime)s [SYSTEM] %(message)s', 
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        system_file_handler.suffix = '%Y-%m-%d'
        system_logger.addHandler(system_file_handler)
        
        # # Also add a root logger handler to catch all logs
        # root_logger = logging.getLogger()
        # root_logger.setLevel(logging.INFO)
        # root_console_handler = logging.StreamHandler()
        # root_console_handler.setLevel(logging.INFO)
        # root_console_handler.setFormatter(logging.Formatter(
        #     '%(asctime)s [ROOT] %(name)s - %(message)s', 
        #     datefmt='%Y-%m-%d %H:%M:%S'
        # ))
        # root_logger.addHandler(root_console_handler)
        
        # Add a simple console handler for immediate visibility
        simple_console_handler = logging.StreamHandler()
        simple_console_handler.setLevel(logging.INFO)
        simple_console_handler.setFormatter(ChinaTimeFormatter(
            '%(asctime)s %(levelname)s: %(message)s', 
            datefmt='%H:%M:%S'
        ))
        system_logger.addHandler(simple_console_handler)

    def get_user_logger(self, username: str) -> logging.Logger:
        """Get or create a logger for a specific user"""
        with self._lock:
            if username not in self.user_loggers:
                self._create_user_logger(username)
            return self.user_loggers[username]

    def _create_user_logger(self, username: str):
        """Create a new logger for a user"""
        # Create user-specific logger
        user_logger = logging.getLogger(f'{username}')
        user_logger.setLevel(logging.INFO)
        # Prevent propagation to parent loggers (important for usernames with dots like email addresses)
        user_logger.propagate = False
        
        # Create user log directory
        user_log_dir = self.logs_dir / username
        user_log_dir.mkdir(exist_ok=True)
        
        # Create handlers
        streaming_handler = UserStreamingLogHandler(username)
        streaming_handler.setLevel(logging.INFO)
        streaming_handler.setFormatter(ChinaTimeFormatter(
            '%(asctime)s %(message)s', 
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        
        file_handler = UserFileLogHandler(username, str(user_log_dir))
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(ChinaTimeFormatter(
            '%(asctime)s %(message)s', 
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        
        # Console handler for user logs
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(ChinaTimeFormatter(
            '%(asctime)s [USER:%(name)s] %(message)s', 
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        
        # Add handlers to logger
        user_logger.addHandler(streaming_handler)
        user_logger.addHandler(file_handler)
        user_logger.addHandler(console_handler)
        
        # Store references
        self.user_loggers[username] = user_logger
        self.user_handlers[username] = {
            'streaming': streaming_handler,
            'file': file_handler,
            'console': console_handler
        }
        
        system_logger.info(f"Created logger for user: {username}")

    def get_streaming_handler(self, username: str) -> Optional[UserStreamingLogHandler]:
        """Get the streaming handler for a user"""
        with self._lock:
            if username in self.user_handlers:
                return self.user_handlers[username]['streaming']
            return None

    def rotate_user_log(self, username: str):
        """Rotate the log file for a user (start new run)"""
        with self._lock:
            if username in self.user_handlers:
                self.user_handlers[username]['file'].rotate_log()
                system_logger.info(f"Rotated log for user: {username}")

    def cleanup_user_logger(self, username: str):
        """Clean up user logger when no longer needed"""
        with self._lock:
            if username in self.user_loggers:
                # Remove handlers
                user_logger = self.user_loggers[username]
                for handler in user_logger.handlers[:]:
                    user_logger.removeHandler(handler)
                
                # Remove from storage
                del self.user_loggers[username]
                del self.user_handlers[username]
                
                system_logger.info(f"Cleaned up logger for user: {username}")

    def get_user_log_files(self, username: str) -> list:
        """Get list of log files for a user"""
        user_log_dir = self.logs_dir / username
        if not user_log_dir.exists():
            return []
        
        log_files = []
        # Support both old format (run_*.log) and new format (YYYY-MM-DD.log)
        for log_file in user_log_dir.glob("*.log"):
            stat = log_file.stat()
            log_files.append({
                'filename': log_file.name,
                'path': str(log_file),
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime, tz=CHINA_TZ).isoformat()
            })
        
        # Sort by modification time (newest first)
        log_files.sort(key=lambda x: x['modified'], reverse=True)
        return log_files

    def get_latest_log_file(self, username: str) -> Optional[str]:
        """Get the path to the latest log file for a user"""
        log_files = self.get_user_log_files(username)
        if log_files:
            return log_files[0]['path']
        return None

    def purge_old_logs(self, username: str, days: int = 10):
        """Delete log files older than specified days for a user"""
        user_log_dir = self.logs_dir / username
        if not user_log_dir.exists():
            return
        
        cutoff_time = datetime.now(tz=CHINA_TZ) - timedelta(days=days)
        cutoff_timestamp = cutoff_time.timestamp()
        
        deleted_count = 0
        deleted_size = 0
        
        for log_file in user_log_dir.glob("*.log"):
            try:
                stat = log_file.stat()
                if stat.st_mtime < cutoff_timestamp:
                    file_size = stat.st_size
                    log_file.unlink()
                    deleted_count += 1
                    deleted_size += file_size
                    system_logger.info(f"Deleted old log file: {log_file.name} (age: {(datetime.now(tz=CHINA_TZ) - datetime.fromtimestamp(stat.st_mtime, tz=CHINA_TZ)).days} days)")
            except Exception as e:
                system_logger.error(f"Failed to delete log file {log_file}: {e}")
        
        if deleted_count > 0:
            size_mb = deleted_size / (1024 * 1024)
            system_logger.info(f"Purged {deleted_count} old log file(s) for user {username}, freed {size_mb:.2f} MB")
    
    def purge_system_log_backups(self, days: int = 30):
        """Purge old system.log backup files older than specified days"""
        if not self.logs_dir.exists():
            return
        
        system_log_path = self.logs_dir / "system.log"
        cutoff_time = datetime.now(tz=CHINA_TZ) - timedelta(days=days)
        cutoff_timestamp = cutoff_time.timestamp()
        
        deleted_count = 0
        deleted_size = 0
        
        # Look for rotated backup files (system.log.YYYY-MM-DD format)
        backup_pattern = re.compile(r'^system\.log\.\d{4}-\d{2}-\d{2}$')
        
        for log_file in self.logs_dir.glob("system.log.*"):
            if log_file.name == "system.log":
                continue  # Skip the main log file
            
            # Check if it matches the backup pattern
            if not backup_pattern.match(log_file.name):
                continue
            
            try:
                stat = log_file.stat()
                if stat.st_mtime < cutoff_timestamp:
                    file_size = stat.st_size
                    log_file.unlink()
                    deleted_count += 1
                    deleted_size += file_size
                    system_logger.info(f"Deleted old system log backup: {log_file.name} (age: {(datetime.now(tz=CHINA_TZ) - datetime.fromtimestamp(stat.st_mtime, tz=CHINA_TZ)).days} days)")
            except Exception as e:
                system_logger.error(f"Failed to delete system log backup {log_file}: {e}")
        
        if deleted_count > 0:
            size_mb = deleted_size / (1024 * 1024)
            system_logger.info(f"Purged {deleted_count} old system log backup file(s), freed {size_mb:.2f} MB")
    
    def purge_all_old_logs(self, days: int = 10):
        """Purge old logs for all users"""
        system_logger.info(f"Starting log purge: removing logs older than {days} days")
        
        if not self.logs_dir.exists():
            return
        
        # Iterate through all user directories
        for user_dir in self.logs_dir.iterdir():
            if user_dir.is_dir() and user_dir.name != 'system.log':
                username = user_dir.name
                self.purge_old_logs(username, days)
        
        # Also clean up old system.log backup files (30-day retention)
        self.purge_system_log_backups(days=30)
        
        system_logger.info("Log purge completed")

# Global instance
user_log_manager = UserLogManager()

# Backward compatibility functions
def setup_logging() -> logging.Logger:
    """Backward compatibility function - returns system logger"""
    return system_logger

def get_stream_handler() -> UserStreamingLogHandler:
    """Backward compatibility function - deprecated, use get_user_stream_handler instead"""
    raise DeprecationWarning("Use get_user_stream_handler(username) instead")

def get_user_stream_handler(username: str) -> Optional[UserStreamingLogHandler]:
    """Get streaming handler for a specific user"""
    return user_log_manager.get_streaming_handler(username)

def get_user_logger(username: str) -> logging.Logger:
    """Get logger for a specific user"""
    return user_log_manager.get_user_logger(username)

# Legacy logger for backward compatibility
logger = system_logger
