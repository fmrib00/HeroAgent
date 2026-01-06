import threading
from typing import Union, List
from datetime import datetime
from log import setup_logging

# Setup logging
logger = setup_logging()

# Global variables that will be set by main.py
active_requests = None
request_lock = None

def set_request_globals(active_requests_dict, request_lock_obj):
    """Set the global request variables from main.py"""
    global active_requests, request_lock
    active_requests = active_requests_dict
    request_lock = request_lock_obj

def get_request_key(username: str, request_type: str, account_names: Union[str, List[str]]) -> str:
    """Generate a unique key for a request to prevent duplicates"""
    if isinstance(account_names, str):
        account_names = [account_names]
    # Sort account names to ensure consistent hashing
    sorted_accounts = sorted(account_names)
    accounts_hash = hash(tuple(sorted_accounts))
    return f"{username}:{request_type}:{accounts_hash}"

def is_request_active(username: str, request_type: str, account_names: Union[str, List[str]]) -> bool:
    """Check if a request is already active for the given user and accounts"""
    if request_lock is None:
        return False
    with request_lock:
        key = get_request_key(username, request_type, account_names)
        return key in active_requests

def mark_request_active(username: str, request_type: str, account_names: Union[str, List[str]]) -> bool:
    """Mark a request as active. Returns False if already active."""
    if request_lock is None:
        return False
    with request_lock:
        key = get_request_key(username, request_type, account_names)
        if key in active_requests:
            return False
        active_requests[key] = {
            'username': username,
            'request_type': request_type,
            'account_names': account_names,
            'start_time': datetime.now()
        }
        return True

def mark_request_inactive(username: str, request_type: str, account_names: Union[str, List[str]]):
    """Mark a request as inactive"""
    if request_lock is None:
        return
    with request_lock:
        key = get_request_key(username, request_type, account_names)
        if key in active_requests:
            del active_requests[key]

def get_active_requests_for_user(username: str) -> List[dict]:
    """Get all active requests for a specific user"""
    if request_lock is None:
        return []
    user_requests = []
    with request_lock:
        for key, request_info in active_requests.items():
            if request_info['username'] == username:
                user_requests.append({
                    'type': request_info['request_type'],
                    'accounts': request_info['account_names'],
                    'start_time': request_info['start_time'].isoformat(),
                    'duration': (datetime.now() - request_info['start_time']).total_seconds()
                })
    return user_requests

def clear_requests_for_user(username: str):
    """Clear all active requests for a specific user"""
    if request_lock is None:
        return
    with request_lock:
        keys_to_remove = []
        for key, request_info in active_requests.items():
            if request_info['username'] == username:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del active_requests[key]
