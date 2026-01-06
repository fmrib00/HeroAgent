from fastapi import HTTPException, Request, Depends, Body
from fastapi.responses import StreamingResponse
import json
import queue
import threading
import os
import requests
from datetime import datetime, timedelta
from typing import Optional

# Import models
from models import (
    LoginRequest, RegisterRequest, AddAccountRequest, InfoRequest,
    ExtractCookiesRequest, ExtractCookiesInteractiveRequest, ExecuteJobRequest,
    OpenBrowserWithCookiesRequest, GoogleLoginRequest
)
from auth_utils import ACCESS_TOKEN_EXPIRE_HOURS

# Helper function to normalize URLs
def normalize_url(url: Optional[str]) -> Optional[str]:
    """
    Normalize a URL by adding 'http://' prefix if it's missing.
    Returns None if url is None or empty, otherwise returns normalized URL.
    """
    if not url or not url.strip():
        return None
    
    url = url.strip()
    
    # If URL doesn't start with http:// or https://, add http://
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url
    
    return url

# Import utility modules
from cache_utils import (
    get_cached_accounts, get_cached_account, get_cached_user_settings,
    update_account_combat_counts, invalidate_user_cache, invalidate_user_settings_cache,
    update_duel_cookies
)
from auth_utils import (
    create_access_token, verify_token, send_email, validate_email_address,
    generate_random_password, check_user_exists, create_user_account, verify_user_credentials
)
from hall_utils import (
    is_hall_combat_running, hall_combat_lock, hall_combat_threads, running_halls,
    stop_combat_for_user
)
from request_utils import get_active_requests_for_user

# Import other dependencies
from character import Character
from log import get_user_logger, get_user_stream_handler, user_log_manager, logger
from pvehall import PVEHall

# Global variables that will be set by main.py
default_hall_setting = {}
heroaccounts_table = None
users_table = None
hall_combat_threads = {}
hall_combat_lock = threading.RLock()
running_halls = {}
request_lock = threading.RLock()
active_requests = {}
hall_stop_events = {}
user_stop_signals = {}
job_scheduler = None
shutdown_requested = None
scheduler_paused = None
scheduler_paused_lock = None
active_jobs = None
active_jobs_lock = None

def set_globals(**kwargs):
    """Set global variables from main.py"""
    global default_hall_setting, users_table, heroaccounts_table
    global hall_combat_threads, hall_combat_lock, running_halls, request_lock
    global active_requests, hall_stop_events, user_stop_signals, job_scheduler
    global shutdown_requested, scheduler_paused, scheduler_paused_lock, active_jobs, active_jobs_lock
    
    for key, value in kwargs.items():
        globals()[key] = value

def get_scheduler_status(current_user: str = Depends(verify_token)):
    """Get scheduler status and next run times"""
    try:
        # Import schedule at module level to ensure we get the same instance
        import schedule
        jobs = schedule.get_jobs()
        
        job_info = []
        for job in jobs:
            job_info.append({
                "job": str(job.job_func),
                "next_run": job.next_run.isoformat() if job.next_run else None,
                "interval": str(job.interval) if hasattr(job, 'interval') else None
            })
        
        return {
            "success": True,
            "scheduler_status": "running",
            "total_jobs": len(jobs),
            "jobs": job_info
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get scheduler status: {str(e)}")

def health_check():
    """Health check endpoint to verify backend is running"""
    try:
        # Count active hall combat sessions
        active_hall_combat_sessions = 0
        with hall_combat_lock:
            for username, thread_info in hall_combat_threads.items():
                active_count = thread_info.get('active_count', 0)
                if active_count > 0:
                    active_hall_combat_sessions += 1

        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "active_requests": len(active_requests),
            "running_halls": sum(len(halls) for halls in running_halls.values()),
            "active_hall_combat_sessions": active_hall_combat_sessions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Health check failed")

# OPTIONS handlers removed - CORS middleware in main.py handles all OPTIONS requests

def register(data: RegisterRequest):
    """Register a new user (player type only).
    
    Note: Admin accounts must be created manually in Azure Table Storage.
    """
    # Validate email
    validate_email_address(data.email)
    
    # Check if user exists
    if check_user_exists(data.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Check user limit
    max_users = int(os.getenv("MAX_USERS", "20"))
    try:
        # Count existing player users
        all_users = list(users_table.list_entities())
        player_count = sum(1 for user in all_users if user.get('user_type', 'player') == 'player')
        
        if player_count >= max_users:
            raise HTTPException(
                status_code=403, 
                detail="已达到最大用户数限制，请联系管理员"
            )
    except HTTPException:
        raise
    except Exception as e:
        # If counting fails, log but don't block registration (fail open)
        logger.warning(f"Failed to count users for limit check: {e}")
    
    # Generate random password
    password = generate_random_password()
    
    try:
        # Create user account (always creates 'player' type - admin accounts must be created manually)
        create_user_account(data.email, password)

        # Compose HTML email
        html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="max-width: 500px; margin: auto; border: 1px solid #eee; border-radius: 10px; padding: 24px; background: #fafafa;">
                    <h2 style="color: #2463c6;">欢迎使用 <a href='https://herohall.us.kg' style='color:#2463c6;text-decoration:none;'>武林英雄离线助手</a>！</h2>
                    <p>您好,</p>
                    <p>感谢注册 <strong>武林英雄离线助手</strong>。</p>
                    <table style='border-collapse:collapse;margin:16px 0;'>
                        <tr>
                            <td style="padding: 8px 12px;">登录账号:</td>
                            <td style="padding: 8px 12px; background: #eee; border-radius:4px;"><strong>{data.email}</strong></td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 12px;">登录密码:</td>
                            <td style="padding: 8px 12px; background: #eee; border-radius:4px;"><strong>{password}</strong></td>
                        </tr>
                    </table>
                    <p>请使用以上账号信息登录离线助手。为保障账号安全，请妥善保管密码，勿向他人泄露。</p>
                    <p>如有任何疑问，欢迎访问我们的官网：</p>
                    <p>
                        <a href="https://herohall.us.kg" target="_blank" style="color:#2463c6;">https://herohall.us.kg</a>
                    </p>
                    <hr style="margin:24px 0;">
                    <small style="color:#888;">此邮件由系统自动发出，请勿回复。</small>
                </div>
            </body>
        </html>
        """
        
        # Send password to email (HTML only)
        send_email(data.email, '武林英雄离线助手', html)
        
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Failed to send email: {str(e)}')

def login(data: LoginRequest):
    """Login user"""
    try:
        # Verify credentials
        entity = verify_user_credentials(data.username, data.password)
        
        # Get user_type from entity (default to 'player' for backward compatibility)
        user_type = entity.get('user_type', 'player')
        # Get advanced field from entity (default to False for backward compatibility)
        advanced = entity.get('advanced', False)
        
        # Refresh user settings cache - this will automatically initialize default job settings
        # if job_settings is null or empty
        from cache_utils import refresh_user_settings_cache
        try:
            refresh_user_settings_cache(data.username)
        except Exception as e:
            logger.debug(f"Could not refresh user settings cache during login for {data.username}: {e}")
        
        # Create access token
        access_token_expires = timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        access_token = create_access_token(
            data={"sub": data.username}, expires_delta=access_token_expires
        )
        
        return {
            "success": True, 
            "access_token": access_token, 
            "token_type": "bearer",
            "user_type": user_type,
            "advanced": advanced
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="账号或密码错误")

async def login_with_google(data: GoogleLoginRequest):
    """Login user with Google OAuth token"""
    try:
        # Verify Google token and get user info
        # Use async HTTP client for non-blocking request
        import httpx
        
        google_user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {"Authorization": f"Bearer {data.token}"}
        
        # Use async httpx for non-blocking request (faster than sync requests)
        # Reduced timeout to 5s for faster failure detection
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(google_user_info_url, headers=headers)
        
        if response.status_code != 200:
            logger.error(f"Google token verification failed: {response.status_code} - {response.text}")
            raise HTTPException(status_code=401, detail="Google登录验证失败")
        
        user_info = response.json()
        email = user_info.get("email")
        
        if not email:
            logger.error("Google user info missing email")
            raise HTTPException(status_code=401, detail="无法获取Google邮箱信息")
        
        # Check if user exists in database
        from auth_utils import check_user_exists, user_table
        
        if not check_user_exists(email):
            logger.warning(f"Google login attempted for non-existent user: {email}")
            raise HTTPException(status_code=401, detail=f"账号 {email} 不存在，请先注册")
        
        # Get user entity (no password check needed for Google login)
        # Use the same method as verify_user_credentials but skip password check
        try:
            entity = user_table.get_entity(partition_key=email, row_key='0')
        except Exception as e:
            logger.error(f"Failed to get user entity for {email}: {e}")
            raise HTTPException(status_code=401, detail="账号不存在")
        
        # Check if account is disabled
        if entity.get('disabled', False):
            raise HTTPException(status_code=401, detail="Account disabled")
        
        # Get user_type from entity (default to 'player' for backward compatibility)
        user_type = entity.get('user_type', 'player')
        # Get advanced field from entity (default to False for backward compatibility)
        advanced = entity.get('advanced', False)
        
        # Check expiration only for player accounts (admin accounts don't expire)
        if user_type == 'player':
            expiration = entity.get('expiration')
            if expiration and expiration < datetime.now().strftime('%Y-%m-%d'):
                raise HTTPException(status_code=401, detail="Account expired")
        
        # Refresh user settings cache
        from cache_utils import refresh_user_settings_cache
        try:
            refresh_user_settings_cache(email)
        except Exception as e:
            logger.debug(f"Could not refresh user settings cache during Google login for {email}: {e}")
        
        # Create access token
        access_token_expires = timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        access_token = create_access_token(
            data={"sub": email}, expires_delta=access_token_expires
        )
        
        logger.info(f"Google login successful for {email}")
        
        return {
            "success": True,
            "access_token": access_token,
            "token_type": "bearer",
            "email": email,
            "username": email,  # For backward compatibility
            "user_type": user_type,
            "advanced": advanced
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google login error: {str(e)}")
        raise HTTPException(status_code=401, detail="Google登录失败")

def refresh_token(request: Request, current_user: str = Depends(verify_token)):
    """Refresh the access token"""
    try:
        # Create new access token using the verified user
        access_token_expires = timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        access_token = create_access_token(
            data={"sub": current_user}, expires_delta=access_token_expires
        )
        
        return {"success": True, "access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Token refresh failed")

def get_accounts(username: str, current_user: str = Depends(verify_token)):
    """Get accounts for a user"""
    # Security: Always use current_user from token, ignore username parameter
    # This ensures users can only access their own accounts
    if username != current_user:
        logger.warning(f"Username mismatch: requested={username}, token={current_user}")
    
    # Use cached accounts instead of database query
    cached_accounts = get_cached_accounts(current_user)
    result = []
    for account_name, account_data in cached_accounts.items():
        acc = {
            "name": account_name,
            "cookie": account_data["cookie"],
            "combat_counts": account_data.get("combat_counts", None),
        }
        # Add hall settings if present
        if account_data["hall_settings"]:
            acc["hall"] = account_data["hall_settings"].copy()
        else:
            acc["hall"] = default_hall_setting.copy()
        # Add common settings if present
        if account_data.get("common_settings"):
            acc["common_settings"] = account_data["common_settings"].copy()
        else:
            acc["common_settings"] = {}
        # Add dungeon settings if present
        if account_data.get("dungeon_settings"):
            acc["dungeon_settings"] = account_data["dungeon_settings"].copy()
        else:
            acc["dungeon_settings"] = []
        # Add duel dungeon settings if present
        if account_data.get("duel_dungeon_settings"):
            acc["duel_dungeon_settings"] = account_data["duel_dungeon_settings"].copy()
        else:
            acc["duel_dungeon_settings"] = []
        result.append(acc)
    
    return result

def add_account(data: AddAccountRequest, current_user: str = Depends(verify_token)):
    """Add or update an account"""
    # Determine target username: admin can add accounts for other users, regular users can only add for themselves
    target_username = current_user
    
    # Check if current user is admin and trying to add account for another user
    if data.username != current_user:
        try:
            admin_entity = users_table.get_entity(partition_key=current_user, row_key='0')
            if admin_entity.get('user_type', 'player') == 'admin':
                # Admin can add accounts for other users
                target_username = data.username
            else:
                # Non-admin users can only add accounts for themselves
                logger.warning(f"Username mismatch in add_account: requested={data.username}, token={current_user}")
                target_username = current_user
        except Exception:
            # If admin check fails, default to current_user for security
            logger.warning(f"Admin check failed in add_account: requested={data.username}, token={current_user}")
            target_username = current_user
    
    # Load existing entity if it exists - use get_entity for more reliable field retrieval
    entity = None
    existing_cookie = None
    try:
        # Try to get the entity directly first (more reliable)
        try:
            entity = heroaccounts_table.get_entity(partition_key=target_username, row_key=data.account_name)
            existing_cookie = entity.get('cookie')
        except Exception:
            # If get_entity fails, try query_entities as fallback
            try:
                existing_entities = list(heroaccounts_table.query_entities(f"PartitionKey eq '{target_username}' and RowKey eq '{data.account_name}'"))
                if existing_entities:
                    entity = existing_entities[0]
                    existing_cookie = entity.get('cookie')
            except Exception as e:
                logger.error(f"Error loading existing entity: {e}")
    except Exception as e:
        # If all methods fail, entity will be None and we'll create a new one
        logger.error(f"Error loading existing entity: {e}")
    
    # CRITICAL: Prevent clearing cookie field - cookie can never be empty or None for existing accounts
    if entity is not None:
        # If updating an existing account, ensure cookie is not being cleared
        if not data.cookie or not data.cookie.strip():
            if existing_cookie:
                # Preserve existing cookie if new one is empty
                logger.warning(f"Attempted to clear cookie for account {data.account_name}, preserving existing cookie")
                data.cookie = existing_cookie
            else:
                # If no existing cookie and new one is empty, this is an error
                raise HTTPException(status_code=400, detail="Cookie cannot be empty when updating an account")
    
    # If entity exists, merge with updates while preserving ALL existing fields
    if entity is not None:
        # Create a copy of the entity to preserve all fields
        # Azure Table Storage requires PartitionKey and RowKey, and we need to preserve all other fields
        updated_entity = {}
        # Copy all existing fields first to ensure nothing is lost
        for key, value in entity.items():
            updated_entity[key] = value
        
        # Ensure PartitionKey and RowKey are set
        updated_entity["PartitionKey"] = target_username
        updated_entity["RowKey"] = data.account_name
        
        # Merge hall_settings
        if data.hall_settings is not None:
            # Load existing hall_settings and merge
            existing_hall = json.loads(updated_entity.get('hall_settings', '{}'))
            for k, v in data.hall_settings.items():
                if k in ["复活重打", "客房补血", "自动买次数", "失败切换"]:
                    existing_hall[k] = bool(v) if v is not None else False
                else:
                    existing_hall[k] = v
            updated_entity["hall_settings"] = json.dumps(existing_hall, ensure_ascii=False)
        
        # Merge common_settings
        if data.common_settings is not None:
            # Load existing common_settings and merge
            existing_common = json.loads(updated_entity.get('common_settings', '{}'))
            for k, v in data.common_settings.items():
                existing_common[k] = v
            updated_entity["common_settings"] = json.dumps(existing_common, ensure_ascii=False)
        
        # Update dungeon_settings (replace entire array, not merge)
        if data.dungeon_settings is not None:
            updated_entity["dungeon_settings"] = json.dumps(data.dungeon_settings, ensure_ascii=False)
        
        # Update duel_dungeon_settings (replace entire array, not merge)
        if data.duel_dungeon_settings is not None:
            updated_entity["duel_dungeon_settings"] = json.dumps(data.duel_dungeon_settings, ensure_ascii=False)
        
        # Update cookie only if new cookie is provided and non-empty (already validated above)
        if data.cookie and data.cookie.strip():
            updated_entity["cookie"] = data.cookie
        
        # Update game_id and password if provided
        if hasattr(data, 'game_id') and data.game_id is not None:
            updated_entity["game_id"] = data.game_id
        if hasattr(data, 'password') and data.password is not None:
            updated_entity["password"] = data.password
        
        # Update combat_counts if provided
        if hasattr(data, 'combat_counts') and data.combat_counts is not None:
            updated_entity["combat_counts"] = data.combat_counts
        
        entity = updated_entity
    else:
        # Create new entity - cookie is required for new accounts
        if not data.cookie or not data.cookie.strip():
            raise HTTPException(status_code=400, detail="Cookie is required when creating a new account")
        
        entity = {
            "PartitionKey": target_username,
            "RowKey": data.account_name,
            "cookie": data.cookie,
        }
        
        # Initialize hall_settings if provided
        if data.hall_settings is not None:
            hall_settings = {}
            for k, v in data.hall_settings.items():
                # Ensure boolean values are stored as boolean
                if k in ["复活重打", "客房补血", "自动买次数", "失败切换"]:
                    hall_settings[k] = bool(v) if v is not None else False
                else:
                    hall_settings[k] = v
            # Serialize hall_settings to JSON string for Azure Table Storage
            entity["hall_settings"] = json.dumps(hall_settings, ensure_ascii=False)
        
        # Initialize common_settings if provided
        if data.common_settings is not None:
            common_settings = {}
            for k, v in data.common_settings.items():
                common_settings[k] = v
            # Serialize common_settings to JSON string for Azure Table Storage
            entity["common_settings"] = json.dumps(common_settings, ensure_ascii=False)
        
        # Initialize dungeon_settings if provided
        if data.dungeon_settings is not None:
            # Serialize dungeon_settings to JSON string for Azure Table Storage
            entity["dungeon_settings"] = json.dumps(data.dungeon_settings, ensure_ascii=False)
        
        # Initialize duel_dungeon_settings if provided
        if data.duel_dungeon_settings is not None:
            # Serialize duel_dungeon_settings to JSON string for Azure Table Storage
            entity["duel_dungeon_settings"] = json.dumps(data.duel_dungeon_settings, ensure_ascii=False)
        
        # Save game_id and password if provided
        if hasattr(data, 'game_id') and data.game_id is not None:
            entity["game_id"] = data.game_id
        if hasattr(data, 'password') and data.password is not None:
            entity["password"] = data.password
        
        # Update combat_counts if provided
        if hasattr(data, 'combat_counts') and data.combat_counts is not None:
            entity["combat_counts"] = data.combat_counts
    
    # Upsert the entity - all fields are now properly preserved
    heroaccounts_table.upsert_entity(entity=entity)
    
    # Invalidate cache for the target user since account data has changed
    invalidate_user_cache(target_username)
    
    return {"success": True}

def get_info(req: InfoRequest, current_user: str = Depends(verify_token)):
    """Get character info"""
    try:
        # Check if admin is accessing on behalf of another user
        username = current_user
        if req.target_username:
            try:
                admin_entity = users_table.get_entity(partition_key=current_user, row_key='0')
                if admin_entity.get('user_type', 'player') != 'admin':
                    raise HTTPException(status_code=403, detail="Admin access required")
                username = req.target_username
            except Exception:
                raise HTTPException(status_code=403, detail="Admin access required")
        
        cached_account = get_cached_account(username, req.account_name)
        if not cached_account:
            # Get all cached accounts for debugging
            all_accounts = get_cached_accounts(username)
            available_accounts = list(all_accounts.keys())
            logger.warning(f"Account '{req.account_name}' not found for user '{username}'. Available accounts: {available_accounts}")
            raise HTTPException(status_code=404, detail=f"Account '{req.account_name}' not found. Available accounts: {available_accounts}")
        
        cookie = cached_account["cookie"]
        # Use user-specific logger
        user_logger = get_user_logger(username)
        char = Character(username, req.account_name, cookie, user_logger)
        info = char.get_info()
        return {"info": info}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_info for user {username}, account {req.account_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

def get_duel_info(req: InfoRequest, current_user: str = Depends(verify_token)):
    """Get character info from duel server (跨服竞技场)"""
    try:
        # Check if admin is accessing on behalf of another user
        username = current_user
        if req.target_username:
            try:
                admin_entity = users_table.get_entity(partition_key=current_user, row_key='0')
                if admin_entity.get('user_type', 'player') != 'admin':
                    raise HTTPException(status_code=403, detail="Admin access required")
                username = req.target_username
            except Exception:
                raise HTTPException(status_code=403, detail="Admin access required")
        
        cached_account = get_cached_account(username, req.account_name)
        if not cached_account:
            # Get all cached accounts for debugging
            all_accounts = get_cached_accounts(username)
            available_accounts = list(all_accounts.keys())
            logger.warning(f"Account '{req.account_name}' not found for user '{username}'. Available accounts: {available_accounts}")
            raise HTTPException(status_code=404, detail=f"Account '{req.account_name}' not found. Available accounts: {available_accounts}")
        
        cookie = cached_account["cookie"]
        duel_cookies = cached_account.get("duel_cookies")  # Load cached duel cookies
        
        # Use user-specific logger
        user_logger = get_user_logger(username)
        char = Character(username, req.account_name, cookie, user_logger, cached_duel_cookies=duel_cookies)
        
        # Get duel server info (now returns structured data)
        duel_info = char.get_duel_info()
        
        return {"info": duel_info}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_duel_info for user {username}, account {req.account_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

def clear_active_requests(username: str, current_user: str = Depends(verify_token)):
    """Clear all active requests for a user (for debugging/manual cleanup)"""
    try:
        with request_lock:
            # Remove all requests for this user
            keys_to_remove = []
            for key, request_info in active_requests.items():
                if request_info['username'] == username:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del active_requests[key]
        
        return {
            "success": True,
            "message": f"Cleared {len(keys_to_remove)} active requests for user {username}",
            "cleared_count": len(keys_to_remove)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear active requests: {str(e)}")

def connection_status(username: str):
    """Get connection status for a user"""
    try:
        # Check if user has any active requests
        user_requests = get_active_requests_for_user(username)
        
        # Check hall combat thread status
        hall_combat_running = is_hall_combat_running(username)
        hall_combat_info = None
        with hall_combat_lock:
            if username in hall_combat_threads:
                thread_info = hall_combat_threads[username]
                active_count = thread_info.get('active_count', 0)
                
                # Only return hall_combat_info if there are actually active threads
                if active_count > 0:
                    hall_combat_info = {
                        'total_threads': len(thread_info['threads']),
                        'active_threads': active_count,
                        'start_time': thread_info['start_time'].isoformat(),
                        'duration': (datetime.now() - thread_info['start_time']).total_seconds()
                    }
        
        return {
            "username": username,
            "active_connections": len(user_requests),
            "requests": user_requests,
            "hall_combat_running": hall_combat_running,
            "hall_combat_info": hall_combat_info
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

def clear_stream_queue(username: str, current_user: str = Depends(verify_token)):
    """Clear the streaming queue for a user"""
    try:
        streaming_handler = get_user_stream_handler(username)
        if not streaming_handler:
            return {"success": False, "message": "No streaming handler found for user"}
        
        # Clear the queue
        cleared_count = 0
        while not streaming_handler.log_queue.empty():
            try:
                streaming_handler.log_queue.get_nowait()
                cleared_count += 1
            except queue.Empty:
                break
        
        return {
            "success": True, 
            "message": f"Cleared {cleared_count} messages from streaming queue",
            "cleared_count": cleared_count
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

def get_log_files(username: str, current_user: str = Depends(verify_token)):
    """Get list of log files for a user"""
    try:
        log_files = user_log_manager.get_user_log_files(username)
        return {"log_files": log_files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

def get_log_file_content(username: str, file_path: str, current_user: str = Depends(verify_token)):
    """Get content of a specific log file for a user"""
    try:
        # Verify the file path belongs to the user (security check)
        log_files = user_log_manager.get_user_log_files(username)
        if not any(log_file['path'] == file_path for log_file in log_files):
            raise HTTPException(status_code=404, detail="Log file not found or access denied")
        
        # Read the file content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            def log_stream():
                try:
                    for line in content.split('\n'):
                        if line.strip():
                            yield f"data: {line.strip()}\n\n"
                    yield f"data: 日志文件读取完成\n\n"
                except Exception as e:
                    yield f"data: Error reading log file: {str(e)}\n\n"
            
            return StreamingResponse(
                log_stream(), 
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                    "Keep-Alive": "timeout=300, max=1000",
                    "Transfer-Encoding": "chunked",
                }
            )
        except (PermissionError, OSError) as e:
            raise HTTPException(status_code=500, detail=f"Failed to read log file: {str(e)}")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

def stop_combat(username: str, current_user: str = Depends(verify_token)):
    """Stop combat for a user"""
    return stop_combat_for_user(username)

def delete_account(request: Request, data: dict = Body(...), current_user: str = Depends(verify_token)):
    """
    Delete an account.
    
    CRITICAL: This function permanently deletes account data including cookies.
    This should only be called from the frontend UI after user confirmation.
    """
    target_username = data.get("username")
    name = data.get("name")
    if not target_username or not name:
        raise HTTPException(status_code=400, detail="Missing username or account name")
    
    # Check if admin is deleting account for another user, or user is deleting their own
    if target_username != current_user:
        try:
            admin_entity = users_table.get_entity(partition_key=current_user, row_key='0')
            if admin_entity.get('user_type', 'player') != 'admin':
                raise HTTPException(status_code=403, detail="Admin access required to delete other users' accounts")
        except Exception:
            raise HTTPException(status_code=403, detail="Admin access required")
    
    # CRITICAL SAFETY CHECK: Verify account exists before deletion
    try:
        existing_entity = heroaccounts_table.get_entity(partition_key=target_username, row_key=name)
        if not existing_entity:
            raise HTTPException(status_code=404, detail=f"Account {name} not found")
    except Exception as e:
        # If get_entity fails with ResourceNotFoundError, account doesn't exist
        if 'ResourceNotFoundError' in str(type(e).__name__) or 'does not exist' in str(e).lower():
            raise HTTPException(status_code=404, detail=f"Account {name} not found")
        # For other errors, log and continue (might be a transient issue)
        logger.warning(f"Error checking account existence before deletion: {e}")
    
    # Log the deletion attempt for audit purposes
    logger.warning(f"User {current_user} is deleting account {name} for user {target_username}")
    
    try:
        heroaccounts_table.delete_entity(partition_key=target_username, row_key=name)
        # Invalidate cache for the target user since account was deleted
        invalidate_user_cache(target_username)
        logger.info(f"Account {name} successfully deleted for user {target_username} by {current_user}")
        return {"success": True, "message": f"Account {name} deleted successfully"}
    except Exception as e:
        logger.error(f"Failed to delete account {name} for user {target_username}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete account: {str(e)}")

def refresh_cache(username: str, current_user: str = Depends(verify_token)):
    """Force refresh cache for a specific user"""
    try:
        from cache_utils import refresh_user_cache
        refresh_user_cache(username)
        return {"success": True, "message": f"Cache refreshed for user {username}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refresh cache: {str(e)}")

def clear_cache(username: str, current_user: str = Depends(verify_token)):
    """Clear cache for a specific user"""
    try:
        invalidate_user_cache(username)
        return {"success": True, "message": f"Cache cleared for user {username}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")

def cache_status(current_user: str = Depends(verify_token)):
    """Get cache status information"""
    from cache_utils import accounts_cache, accounts_cache_lock
    with accounts_cache_lock:
        cache_info = {
            "total_users_cached": len(accounts_cache),
            "users": list(accounts_cache.keys()),
            "user_account_counts": {username: len(accounts) for username, accounts in accounts_cache.items()}
        }
    return {"success": True, "cache_info": cache_info}

def _get_user_settings_helper(username: str):
    """Helper function to get user settings"""
    user_settings = get_cached_user_settings(username)
    
    # Parse job_settings if it exists
    job_settings = {}
    try:
        job_settings_str = user_settings.get("job_settings", "{}")
        job_settings = json.loads(job_settings_str) if job_settings_str else {}
    except (json.JSONDecodeError, TypeError):
        job_settings = {}
    
    return {
        "success": True,
        "job_settings": job_settings,
        "job_scheduling_enabled": user_settings.get("job_scheduling_enabled", True)
    }

def get_user_settings(request: Request, current_user: str = Depends(verify_token)):
    """Get user settings including job_settings"""
    try:
        # Check if admin is requesting settings for another user
        target_username = request.query_params.get('target_username')
        if target_username and target_username != current_user:
            # Verify current user is admin
            try:
                admin_entity = users_table.get_entity(partition_key=current_user, row_key='0')
                if admin_entity.get('user_type', 'player') != 'admin':
                    raise HTTPException(status_code=403, detail="Admin access required")
                username = target_username
            except Exception:
                raise HTTPException(status_code=403, detail="Admin access required")
        else:
            username = current_user
        
        return _get_user_settings_helper(username)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get user settings: {str(e)}")

def get_jobs_table(current_user: str = Depends(verify_token)):
    """Get the complete jobs configuration table"""

    user_settings = _get_user_settings_helper(current_user)
    user_jobs = user_settings.get("job_settings", {})

    available_jobs = job_scheduler.available_jobs()
    for job_id, job_config in available_jobs.items():
        if job_id in user_jobs:
            user_job_config = user_jobs[job_id]
            job_config['enabled'] = user_job_config.get('enabled', False)
            job_config['type'] = user_job_config.get('type', 'daily')
            
            # Set fields based on job type
            job_type = user_job_config.get('type', 'daily')
            if job_type == 'hourly':
                # Hourly jobs only have minute
                job_config['minute'] = user_job_config.get('minute', '0')
            elif job_type == 'daily':
                # Daily jobs have hour and minute
                job_config['hour'] = user_job_config.get('hour', '0')
                job_config['minute'] = user_job_config.get('minute', '0')
            elif job_type == 'weekly':
                # Weekly jobs have day_of_week, hour, and minute
                job_config['day_of_week'] = user_job_config.get('day_of_week', '0')
                job_config['hour'] = user_job_config.get('hour', '0')
                job_config['minute'] = user_job_config.get('minute', '0')
    
    # Also refresh user settings cache to ensure we have the latest data
    from cache_utils import refresh_user_settings_cache
    try:
        refresh_user_settings_cache(current_user)
    except Exception as e:
        logger.warning(f"Failed to refresh user settings cache for {current_user}: {e}")
    
    return {
        "success": True,
        "jobs_table": available_jobs
    }

def get_job_scheduler_status(current_user: str = Depends(verify_token)):
    """Get the current status of the job scheduler"""
    try:
        return {
            "success": True,
            "job_scheduler": {
                "registered_job_types": list(job_scheduler.job_registry.keys()),
                "total_job_types": len(job_scheduler.job_registry),
                "available_job_types": ["DAILY", "HOURLY", "WEEKLY", "CUSTOM"]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get job scheduler status: {str(e)}")

def set_job_settings(request: Request, data: dict = Body(...), current_user: str = Depends(verify_token)):
    """Set job settings for a user"""
    try:
        username = data.get('username')
        job_settings = data.get('job_settings', {})
        job_scheduling_enabled = data.get('job_scheduling_enabled', True)
        
        if not username:
            raise HTTPException(status_code=400, detail="Username is required")
        
        # Check if admin is setting settings for another user
        if username != current_user:
            # Verify current user is admin
            try:
                admin_entity = users_table.get_entity(partition_key=current_user, row_key='0')
                if admin_entity.get('user_type', 'player') != 'admin':
                    raise HTTPException(status_code=403, detail="Admin access required")
            except Exception:
                raise HTTPException(status_code=403, detail="Admin access required")
        
        # Validate job settings
        for job_id, settings in job_settings.items():
            # Validate hour and minute for daily jobs
            if settings['type'] == 'daily':
                hour = settings.get('hour')
                if hour is None:
                    raise HTTPException(status_code=400, detail=f"Missing hour for daily job {job_id}")
                try:
                    hour = int(hour)
                    if hour < 0 or hour > 23:
                        raise HTTPException(status_code=400, detail=f"Invalid hour for daily job {job_id}: {hour}")
                except (ValueError, TypeError):
                    raise HTTPException(status_code=400, detail=f"Invalid hour for daily job {job_id}: {hour}")
                
                minute = settings.get('minute', 0)
                try:
                    minute = int(minute)
                    if minute < 0 or minute > 59:
                        raise HTTPException(status_code=400, detail=f"Invalid minute for daily job {job_id}: {minute}")
                except (ValueError, TypeError):
                    raise HTTPException(status_code=400, detail=f"Invalid minute for daily job {job_id}: {minute}")
            
            # Validate day_of_week and hour for weekly jobs
            if settings['type'] == 'weekly':
                day_of_week = settings.get('day_of_week')
                if day_of_week is None:
                    raise HTTPException(status_code=400, detail=f"Missing day_of_week for weekly job {job_id}")
                try:
                    day_of_week = int(day_of_week)
                    if day_of_week < 0 or day_of_week > 6:
                        raise HTTPException(status_code=400, detail=f"Invalid day_of_week for weekly job {job_id}: {day_of_week}")
                except (ValueError, TypeError):
                    raise HTTPException(status_code=400, detail=f"Invalid day_of_week for weekly job {job_id}: {day_of_week}")
                
                hour = settings.get('hour')
                if hour is None:
                    raise HTTPException(status_code=400, detail=f"Missing hour for weekly job {job_id}")
                try:
                    hour = int(hour)
                    if hour < 0 or hour > 23:
                        raise HTTPException(status_code=400, detail=f"Invalid hour for weekly job {job_id}: {hour}")
                except (ValueError, TypeError):
                    raise HTTPException(status_code=400, detail=f"Invalid hour for weekly job {job_id}: {hour}")
        
        # Get existing user entity
        try:
            user_entity = users_table.get_entity(partition_key=username, row_key='0')
        except Exception:
            # User doesn't exist, create new entity
            user_entity = {
                "PartitionKey": username,
                "RowKey": "0"
            }
        
        # Update job settings and master toggle
        user_entity["job_settings"] = json.dumps(job_settings)
        user_entity["job_scheduling_enabled"] = job_scheduling_enabled
        
        # Save to table
        users_table.upsert_entity(user_entity)
        
        # Invalidate user settings cache since settings have changed
        invalidate_user_settings_cache(username)
        
        return {
            "success": True,
            "message": "Job settings updated successfully",
            "saved_settings": job_settings
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set job settings: {str(e)}")

def debug_user_settings(username: str, current_user: str = Depends(verify_token)):
    """Debug endpoint to check user settings"""
    try:
        # Get raw entity from database
        try:
            raw_entity = users_table.get_entity(partition_key=username, row_key='0')
        except Exception:
            raw_entity = None
        
        # Get cached settings
        cached_settings = get_cached_user_settings(username)
        
        # Parse job_settings
        job_settings = {}
        if raw_entity and raw_entity.get("job_settings"):
            try:
                job_settings = json.loads(raw_entity["job_settings"])
            except (json.JSONDecodeError, TypeError):
                job_settings = {}
        
        return {
            "success": True,
            "raw_entity": raw_entity,
            "cached_settings": cached_settings,
            "parsed_job_settings": job_settings
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get debug user settings: {str(e)}")

def buy_combat_count(req: InfoRequest, current_user: str = Depends(verify_token)):
    """Buy one combat count for a character and reset combat_counts in database"""
    try:
        # Use cached account data instead of database query
        cached_account = get_cached_account(current_user, req.account_name)
        if not cached_account:
            raise HTTPException(status_code=404, detail="Account not found")
        cookie = cached_account["cookie"]
        
        # Use user-specific logger instead of global logger
        user_logger = get_user_logger(current_user)
        char = Character(current_user, req.account_name, cookie, user_logger)
        
        # Call buy_combat_count method
        ret = char.buy_combat_count()
        
        # Reset combat_counts field in database to None after buying
        try:
            entity = heroaccounts_table.get_entity(partition_key=current_user, row_key=req.account_name)
            entity["combat_counts"] = None
            heroaccounts_table.upsert_entity(entity)
            
            # Invalidate cache for this user since account data has changed
            invalidate_user_cache(current_user)
            
            user_logger.info(f'{req.account_name}: 已重置数据库中的战斗次数字段')
        except Exception as e:
            user_logger.warning(f'{req.account_name}: 重置数据库战斗次数字段失败: {e}')
        
        return {
            "success": True, 
            "message": f"角色 {req.account_name} {ret}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"购买挑战次数失败: {str(e)}")

def execute_job_manually(req: ExecuteJobRequest, current_user: str = Depends(verify_token)):
    """Manually execute a specific job for a user"""
    try:
        username = current_user
        if req.target_username:
            try:
                if users_table is None:
                    from endpoints import users_table as endpoints_users_table
                    admin_entity = endpoints_users_table.get_entity(partition_key=current_user, row_key='0')
                else:
                    admin_entity = users_table.get_entity(partition_key=current_user, row_key='0')
                if admin_entity.get('user_type', 'player') != 'admin':
                    raise HTTPException(status_code=403, detail="Admin access required")
                username = req.target_username
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(status_code=403, detail="Admin access required")
        user_logger = get_user_logger(username)
        
        # Get account selection from request data
        account_names = req.account_names or []
        if not account_names:
            # If no accounts specified, get all accounts for the user
            cached_accounts = get_cached_accounts(username)
            account_names = list(cached_accounts.keys())
        
        # Check if job scheduler is available
        if not job_scheduler:
            raise HTTPException(status_code=500, detail="Job scheduler not available")
        
        # Check if the job exists in the executor manager
        if req.job_id not in job_scheduler.executor_manager.executors:
            raise HTTPException(status_code=404, detail=f"Job '{req.job_id}' not found")
        
        # Execute the job manually with account selection
        try:
            user_logger.info(f"Manually executing job: {req.job_id} for accounts: {account_names}")
            job_config = {'account_names': account_names}
            job_scheduler.executor_manager.execute_job(req.job_id, username, job_config)
            user_logger.info(f"Successfully executed job: {req.job_id}")
            
            return {
                "success": True,
                "message": f"任务 '{job_scheduler.executor_manager.executors[req.job_id][1]}' 已手动执行"
            }
        except Exception as e:
            user_logger.error(f"Error executing job {req.job_id}: {e}")
            raise HTTPException(status_code=500, detail=f"执行任务失败: {str(e)}")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行任务失败: {str(e)}")

def execute_command(data: dict = Body(...), current_user: str = Depends(verify_token)):
    """Execute a command for selected accounts"""
    try:
        command = data.get('command')
        if not command:
            raise HTTPException(status_code=400, detail="command is required")
        
        # Check if current user is admin and target_username is provided
        target_username = data.get('target_username')
        if target_username:
            # Verify current user is admin
            try:
                admin_entity = users_table.get_entity(partition_key=current_user, row_key='0')
                if admin_entity.get('user_type', 'player') != 'admin':
                    raise HTTPException(status_code=403, detail="Admin access required")
                username = target_username
            except Exception:
                raise HTTPException(status_code=403, detail="Admin access required")
        else:
            username = current_user
        
        user_logger = get_user_logger(username)
        
        # Get account selection from request data
        account_names = data.get('account_names', [])
        if not account_names:
            raise HTTPException(status_code=400, detail="account_names is required")
        
        # Get optional id parameter
        command_id = data.get('id')
        
        # Get optional is_duel_command parameter
        is_duel_command = data.get('is_duel_command', False)
        
        # Get cached accounts
        cached_accounts = get_cached_accounts(username)
        
        results = {}
        for account_name in account_names:
            if account_name not in cached_accounts:
                results[account_name] = {"success": False, "error": "Account not found"}
                continue
            
            try:
                account_data = cached_accounts[account_name]
                duel_cookies = account_data.get('duel_cookies')
                character = Character(username, account_name, account_data['cookie'], user_logger, cached_duel_cookies=duel_cookies)
                
                # Execute the command
                command_prefix = "[跨服] " if is_duel_command else ""
                user_logger.info(f"{command_prefix}Executing command '{command}' for {account_name}" + (f" with ID: {command_id}" if command_id else ""))
                if '/' in command:
                    ret = character.command(command=None, link=command, id=command_id, is_duel_command=is_duel_command)
                else:
                    ret = character.command(command=command, id=command_id, is_duel_command=is_duel_command)
                
                # Save duel cookies to cache if it was a duel command
                if is_duel_command and character.command.duel_cookies:
                    update_duel_cookies(username, account_name, character.command.duel_cookies)
                
                results[account_name] = {"success": True, "message": ret}
                user_logger.info(f"{command_prefix}Successfully executed command '{command}' for {account_name}")
                
            except Exception as e:
                user_logger.error(f"Error executing command '{command}' for {account_name}: {e}")
                results[account_name] = {"success": False, "error": str(e)}
        
        command_type = "跨服命令" if is_duel_command else "命令"
        return {
            "success": True,
            "results": results,
            "message": f"{command_type} '{command}' 已对 {len(account_names)} 个账号执行"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行命令失败: {str(e)}")

def olympics(data: dict = Body(...), current_user: str = Depends(verify_token)):
    """Register for olympics competition for selected accounts"""
    try:
        match_type = data.get('type')
        if not match_type:
            raise HTTPException(status_code=400, detail="type is required")
        
        # Check if admin is accessing on behalf of another user
        target_username = data.get('target_username')
        if target_username:
            try:
                admin_entity = users_table.get_entity(partition_key=current_user, row_key='0')
                if admin_entity.get('user_type', 'player') != 'admin':
                    raise HTTPException(status_code=403, detail="Admin access required")
                username = target_username
            except Exception:
                raise HTTPException(status_code=403, detail="Admin access required")
        else:
            username = current_user
        user_logger = get_user_logger(username)
        
        # Get account selection from request data
        account_names = data.get('account_names', [])
        if not account_names:
            raise HTTPException(status_code=400, detail="account_names is required")
        
        # Get cached accounts
        cached_accounts = get_cached_accounts(username)
        
        results = {}
        for account_name in account_names:
            if account_name not in cached_accounts:
                results[account_name] = {"success": False, "error": "Account not found"}
                continue
            
            try:
                account_data = cached_accounts[account_name]
                duel_cookies = account_data.get('duel_cookies')
                character = Character(username, account_name, account_data['cookie'], user_logger, cached_duel_cookies=duel_cookies)
                
                # Call olympics function
                user_logger.info(f"Registering for olympics '{match_type}' for {account_name}")
                ret = character.olympics(match_type)
                try:
                    ret = json.loads(ret) if isinstance(ret, str) else ret
                except Exception as e:
                    if '纵横天下' in ret:
                        ret = {'result': '报名成功', 'error': False}
                    else:
                        raise
                
                # Save duel cookies to cache if it was a duel command
                if character.command.duel_cookies:
                    update_duel_cookies(username, account_name, character.command.duel_cookies)
                
                result_text = ret.get('result')
                results[account_name] = {"success": not ret.get('error'), "message": result_text}
                user_logger.info(f"{account_name}: register for olympics '{match_type}' {result_text}")
                
            except Exception as e:
                user_logger.error(f"Error registering for olympics '{match_type}' for {account_name}: {e}")
                results[account_name] = {"success": False, "error": str(e)}
        
        return {
            "success": True,
            "results": results,
            "message": f"报名比赛 '{match_type}' 已对 {len(account_names)} 个账号执行"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"报名比赛失败: {str(e)}")

def zongheng_challenge(data: dict = Body(...), current_user: str = Depends(verify_token)):
    """Execute zongheng_challenge for selected accounts"""
    try:
        # Check if admin is accessing on behalf of another user
        target_username = data.get('target_username')
        if target_username:
            try:
                admin_entity = users_table.get_entity(partition_key=current_user, row_key='0')
                if admin_entity.get('user_type', 'player') != 'admin':
                    raise HTTPException(status_code=403, detail="Admin access required")
                username = target_username
            except Exception:
                raise HTTPException(status_code=403, detail="Admin access required")
        else:
            username = current_user
        user_logger = get_user_logger(username)
        
        # Get account selection from request data
        account_names = data.get('account_names', [])
        if not account_names:
            raise HTTPException(status_code=400, detail="account_names is required")
        
        # Get cached accounts
        cached_accounts = get_cached_accounts(username)
        
        results = {}
        for account_name in account_names:
            if account_name not in cached_accounts:
                results[account_name] = {"success": False, "error": "Account not found"}
                continue
            
            try:
                account_data = cached_accounts[account_name]
                duel_cookies = account_data.get('duel_cookies')
                character = Character(username, account_name, account_data['cookie'], user_logger, cached_duel_cookies=duel_cookies)
                
                # Call zongheng_challenge function
                user_logger.info(f"Executing zongheng_challenge for {account_name}")
                ret = character.zongheng_challenge()
                
                # Save duel cookies to cache if it was a duel command
                if character.command.duel_cookies:
                    update_duel_cookies(username, account_name, character.command.duel_cookies)
                
                if ret is None:
                    results[account_name] = {"success": False, "error": "Failed to execute zongheng_challenge"}
                else:
                    results[account_name] = {"success": True, "message": ret}
                user_logger.info(f"{account_name}: zongheng_challenge completed")
                
            except Exception as e:
                user_logger.error(f"Error executing zongheng_challenge for {account_name}: {e}")
                results[account_name] = {"success": False, "error": str(e)}
        
        return {
            "success": True,
            "results": results,
            "message": f"纵横天下挑战已对 {len(account_names)} 个账号执行"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"纵横天下挑战失败: {str(e)}")

def buy_duel_medal(data: dict = Body(...), current_user: str = Depends(verify_token)):
    """Buy duel medal for selected accounts"""
    try:
        # Check if admin is accessing on behalf of another user
        target_username = data.get('target_username')
        if target_username:
            try:
                admin_entity = users_table.get_entity(partition_key=current_user, row_key='0')
                if admin_entity.get('user_type', 'player') != 'admin':
                    raise HTTPException(status_code=403, detail="Admin access required")
                username = target_username
            except Exception:
                raise HTTPException(status_code=403, detail="Admin access required")
        else:
            username = current_user
        user_logger = get_user_logger(username)
        
        # Get account selection from request data
        account_names = data.get('account_names', [])
        if not account_names:
            raise HTTPException(status_code=400, detail="account_names is required")
        
        # Get big_package flag from request data (default True for backwards compatibility)
        big_package = data.get('big_package', True)
        
        # Get cached accounts
        cached_accounts = get_cached_accounts(username)
        
        results = {}
        results_lock = threading.Lock()
        
        def process_account(account_name: str):
            """Process a single account in a thread"""
            if account_name not in cached_accounts:
                with results_lock:
                    results[account_name] = {"success": False, "error": "Account not found"}
                return
            
            try:
                account_data = cached_accounts[account_name]
                duel_cookies = account_data.get('duel_cookies')
                character = Character(username, account_name, account_data['cookie'], user_logger, cached_duel_cookies=duel_cookies)
                
                # Call buy_duel_medal function
                package_type = "大" if big_package else "单个"
                user_logger.info(f"{account_name}: 购买通用粉丝团徽章礼包({package_type})")
                ret = character.buy_duel_medal(big_package=big_package)
                with results_lock:
                    results[account_name] = {"success": not ret.get('error'), "message": ret.get('message')}
            except Exception as e:
                package_type = "大" if big_package else "单个"
                user_logger.error(f"{account_name}: 购买通用粉丝团徽章礼包({package_type})失败: {e}")
                with results_lock:
                    results[account_name] = {"success": False, "error": str(e)}
        
        # Create and start threads for each account
        threads = []
        for account_name in account_names:
            thread = threading.Thread(
                target=process_account,
                args=(account_name,),
                name=f"buy_duel_medal_{account_name}"
            )
            thread.start()
            threads.append(thread)
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        return {
            "success": True,
            "results": results,
            "message": f"买通用徽章 已对 {len(account_names)} 个账号执行"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        user_logger.error(f"买通用徽章失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def get_fan_badges(data: dict = Body(...), current_user: str = Depends(verify_token)):
    """Get fan badges for selected accounts"""
    try:
        # Check if admin is accessing on behalf of another user
        target_username = data.get('target_username')
        if target_username:
            try:
                admin_entity = users_table.get_entity(partition_key=current_user, row_key='0')
                if admin_entity.get('user_type', 'player') != 'admin':
                    raise HTTPException(status_code=403, detail="Admin access required")
                username = target_username
            except Exception:
                raise HTTPException(status_code=403, detail="Admin access required")
        else:
            username = current_user
        user_logger = get_user_logger(username)
        # Get account selection from request data
        account_names = data.get('account_names', [])
        if not account_names:
            user_logger.warning("获取粉丝徽章列表失败: account_names为空")
            raise HTTPException(status_code=400, detail="account_names is required")
        
        # Get cached accounts
        cached_accounts = get_cached_accounts(username)
        
        results = {}
        for account_name in account_names:
            if account_name not in cached_accounts:
                results[account_name] = {"success": False, "error": "Account not found"}
                continue
            try:
                account_data = cached_accounts[account_name]
                duel_cookies = account_data.get('duel_cookies')
                character = Character(username, account_name, account_data['cookie'], user_logger, cached_duel_cookies=duel_cookies)
                
                # Call get_all_fan_badges function
                user_logger.info(f"{account_name}: 获取粉丝徽章列表")
                badges = character.get_all_fan_badges()
                if badges is None:
                    results[account_name] = {"success": False, "error": "无法获取粉丝徽章列表"}
                else:
                    # badges can be an empty list if no badges found, which is still a success
                    results[account_name] = {"success": True, "message": json.dumps(badges, ensure_ascii=False, indent=2)}
            except Exception as e:
                user_logger.error(f"{account_name}: 获取粉丝徽章列表失败: {e}")
                results[account_name] = {"success": False, "error": str(e)}
        
        return {
            "success": True,
            "results": results,
            "message": f"获取粉丝徽章列表 已对 {len(account_names)} 个账号执行"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        user_logger.error(f"获取粉丝徽章列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def exchange_fan_badge(data: dict = Body(...), current_user: str = Depends(verify_token)):
    """Exchange fan badge for selected accounts"""
    try:
        # Check if admin is accessing on behalf of another user
        target_username = data.get('target_username')
        if target_username:
            try:
                admin_entity = users_table.get_entity(partition_key=current_user, row_key='0')
                if admin_entity.get('user_type', 'player') != 'admin':
                    raise HTTPException(status_code=403, detail="Admin access required")
                username = target_username
            except Exception:
                raise HTTPException(status_code=403, detail="Admin access required")
        else:
            username = current_user
        user_logger = get_user_logger(username)
        
        # Get account selection and badge info from request data
        account_names = data.get('account_names', [])
        badge_name = data.get('badge_name')
        badge_id = data.get('badge_id')
        required_item = data.get('required_item')
        required_quantity = data.get('required_quantity')  # Total required quantity
        exchange_quantity = data.get('exchange_quantity', 1)  # Number of badges to exchange
        
        if not account_names:
            raise HTTPException(status_code=400, detail="account_names is required")
        if not badge_name or not badge_id:
            raise HTTPException(status_code=400, detail="badge_name and badge_id are required")
        if not required_item:
            raise HTTPException(status_code=400, detail="required_item is required")
        
        # Get cached accounts
        cached_accounts = get_cached_accounts(username)
        
        results = {}
        results_lock = threading.Lock()
        
        def process_account(account_name: str):
            """Process a single account in a thread"""
            if account_name not in cached_accounts:
                with results_lock:
                    results[account_name] = {"success": False, "error": "Account not found"}
                return
            
            try:
                account_data = cached_accounts[account_name]
                duel_cookies = account_data.get('duel_cookies')
                character = Character(username, account_name, account_data['cookie'], user_logger, cached_duel_cookies=duel_cookies)
                result = character.exchange_fan_badge(
                    badge_name=badge_name,
                    badge_id=badge_id,
                    required_item=required_item,
                    required_quantity=required_quantity,
                    exchange_quantity=exchange_quantity,
                )
                with results_lock:
                    results[account_name] = result
            except Exception as e:
                user_logger.error(f"{account_name}: 兑换粉丝徽章失败: {e}")
                with results_lock:
                    results[account_name] = {"success": False, "error": str(e)}
        
        # Create and start threads for each account
        threads = []
        for account_name in account_names:
            thread = threading.Thread(
                target=process_account,
                args=(account_name,),
                name=f"exchange_fan_badge_{account_name}"
            )
            thread.start()
            threads.append(thread)
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        return {
            "success": True,
            "results": results,
            "message": f"粉丝章兑换 已对 {len(account_names)} 个账号执行"
        }        
    except HTTPException:
        raise
    except Exception as e:
        user_logger.error(f"粉丝章兑换失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def lottery(data: dict = Body(...), current_user: str = Depends(verify_token)):
    """Execute lottery for selected accounts"""
    try:
        lottery_type = data.get('type')
        if not lottery_type:
            raise HTTPException(status_code=400, detail="type is required")
        
        # Check if admin is accessing on behalf of another user
        target_username = data.get('target_username')
        if target_username:
            try:
                admin_entity = users_table.get_entity(partition_key=current_user, row_key='0')
                if admin_entity.get('user_type', 'player') != 'admin':
                    raise HTTPException(status_code=403, detail="Admin access required")
                username = target_username
            except Exception:
                raise HTTPException(status_code=403, detail="Admin access required")
        else:
            username = current_user
        user_logger = get_user_logger(username)
        
        # Get account selection from request data
        account_names = data.get('account_names', [])
        if not account_names:
            raise HTTPException(status_code=400, detail="account_names is required")
        
        # Get lottery numbers from request data
        lottery_numbers = data.get('lottery_numbers', '')
        if not lottery_numbers:
            raise HTTPException(status_code=400, detail="lottery_numbers is required")
        
        # Validate lottery_numbers contains only digits
        if not lottery_numbers.isdigit():
            raise HTTPException(status_code=400, detail="lottery_numbers must contain only digits")
        
        # Get cached accounts
        cached_accounts = get_cached_accounts(username)
        
        results = {}
        for account_name in account_names:
            if account_name not in cached_accounts:
                results[account_name] = {"success": False, "error": "Account not found"}
                continue
            
            try:
                account_data = cached_accounts[account_name]
                duel_cookies = account_data.get('duel_cookies')
                character = Character(username, account_name, account_data['cookie'], user_logger, cached_duel_cookies=duel_cookies)
                
                # Call submit_lottery_votes function
                from lottery import submit_lottery_votes
                user_logger.info(f"Submitting lottery '{lottery_type}' with numbers '{lottery_numbers}' for {account_name}")
                submit_lottery_votes(character, lottery_type, lottery_numbers)
                
                # Save duel cookies to cache if it was a duel command
                if character.command.duel_cookies:
                    update_duel_cookies(username, account_name, character.command.duel_cookies)
                
                results[account_name] = {"success": True, "message": f"联赛竞猜 '{lottery_type}' 号码 '{lottery_numbers}' 提交成功"}
                user_logger.info(f"{account_name}: lottery '{lottery_type}' with numbers '{lottery_numbers}' submitted successfully")
                
            except Exception as e:
                user_logger.error(f"Error executing lottery '{lottery_type}' for {account_name}: {e}")
                results[account_name] = {"success": False, "error": str(e)}
        
        return {
            "success": True,
            "results": results,
            "message": f"联赛竞猜 '{lottery_type}' 已对 {len(account_names)} 个账号执行"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"联赛竞猜失败: {str(e)}")

def auto_gift(data: dict = Body(...), current_user: str = Depends(verify_token)):
    """Claim gift packages for selected accounts"""
    try:
        # Check if admin is accessing on behalf of another user
        target_username = data.get('target_username')
        if target_username:
            try:
                admin_entity = users_table.get_entity(partition_key=current_user, row_key='0')
                if admin_entity.get('user_type', 'player') != 'admin':
                    raise HTTPException(status_code=403, detail="Admin access required")
                username = target_username
            except Exception:
                raise HTTPException(status_code=403, detail="Admin access required")
        else:
            username = current_user
        user_logger = get_user_logger(username)
        
        # Get account selection from request data
        account_names = data.get('account_names', [])
        if not account_names:
            raise HTTPException(status_code=400, detail="account_names is required")
        
        # Get cached accounts
        cached_accounts = get_cached_accounts(username)
        
        results = {}
        for account_name in account_names:
            if account_name not in cached_accounts:
                results[account_name] = {"success": False, "error": "Account not found"}
                continue
            
            try:
                account_data = cached_accounts[account_name]
                character = Character(username, account_name, account_data['cookie'], user_logger)
                
                # Call auto_gift function
                user_logger.info(f"{account_name}: 领取礼包")
                ret = character.auto_gift()
                results[account_name] = {"success": True, "message": "礼包领取完成: " + ret}
            except Exception as e:
                user_logger.error(f"{account_name}: 领取礼包失败: {e}")
                results[account_name] = {"success": False, "error": str(e)}
        
        return {
            "success": True,
            "results": results,
            "message": f"领取礼包 已对 {len(account_names)} 个账号执行"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"领取礼包失败: {str(e)}")

async def extract_cookies(req: ExtractCookiesRequest, current_user: str = Depends(verify_token)):
    """
    Automatically extract game cookies by logging in with username and password.
    This endpoint uses Playwright to automate the login process and extract cookies.
    """
    try:
        from cookie_extractor import extract_cookies as extract_cookies_async
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        # Normalize the URL - add http:// if missing
        normalized_url = normalize_url(req.url)
        
        def run_playwright():
            """Run Playwright in a separate thread with its own event loop"""
            # Set event loop policy for Windows subprocess support
            import sys
            if sys.platform == 'win32':
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(extract_cookies_async(
                    username=req.username,
                    password=req.password,
                    game_url=normalized_url,
                    timeout=req.timeout or 60
                ))
            finally:
                loop.close()
        
        # Run Playwright in a thread pool executor to avoid event loop conflicts
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, run_playwright)
        
        if result['success']:
            return {
                "success": True,
                "cookie_string": result['cookie_string'],
                "weeCookie": result['weeCookie'],
                "50hero_session": result['50hero_session'],
                "message": "Cookies extracted successfully"
            }
        else:
            raise HTTPException(status_code=400, detail=f"Failed to extract cookies: {result.get('error', 'Unknown error')}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extracting cookies: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to extract cookies: {str(e)}")

def get_all_players(current_user: str = Depends(verify_token)):
    """Get list of all player users (admin only)"""
    try:
        # Check if current user is admin
        try:
            admin_entity = users_table.get_entity(partition_key=current_user, row_key='0')
            if admin_entity.get('user_type', 'player') != 'admin':
                raise HTTPException(status_code=403, detail="Admin access required")
        except Exception:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Query all users
        all_users = list(users_table.list_entities())
        
        # Filter to only player users
        players = []
        for user in all_users:
            user_type = user.get('user_type', 'player')
            if user_type == 'player':
                player_email = user.get('PartitionKey')
                # Get account count for this player
                try:
                    cached_accounts = get_cached_accounts(player_email)
                    account_count = len(cached_accounts) if cached_accounts else 0
                except Exception:
                    account_count = 0
                
                players.append({
                    'email': player_email,
                    'disabled': user.get('disabled', False),
                    'expiration': user.get('expiration', ''),
                    'user_type': user_type,
                    'advanced': user.get('advanced', False),
                    'account_count': account_count
                })
        
        return {
            "success": True,
            "players": players,
            "total": len(players)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting players list: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get players list: {str(e)}")

def get_player_accounts(player_email: str, current_user: str = Depends(verify_token)):
    """Get accounts for a specific player user (admin only)"""
    try:
        # Check if current user is admin
        try:
            admin_entity = users_table.get_entity(partition_key=current_user, row_key='0')
            if admin_entity.get('user_type', 'player') != 'admin':
                raise HTTPException(status_code=403, detail="Admin access required")
        except Exception:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Verify player exists and is a player type
        try:
            player_entity = users_table.get_entity(partition_key=player_email, row_key='0')
            if player_entity.get('user_type', 'player') != 'player':
                raise HTTPException(status_code=400, detail="User is not a player")
        except Exception:
            raise HTTPException(status_code=404, detail="Player not found")
        
        # Get accounts for this player (same logic as get_accounts but for admin)
        cached_accounts = get_cached_accounts(player_email)
        result = []
        for account_name, account_data in cached_accounts.items():
            acc = {
                "name": account_name,
                "cookie": account_data["cookie"],
                "combat_counts": account_data.get("combat_counts", None),
            }
            # Add hall settings if present
            if account_data["hall_settings"]:
                acc["hall"] = account_data["hall_settings"].copy()
            else:
                acc["hall"] = default_hall_setting.copy()
            # Add common settings if present
            if account_data.get("common_settings"):
                acc["common_settings"] = account_data["common_settings"].copy()
            else:
                acc["common_settings"] = {}
            # Add dungeon settings if present
            if account_data.get("dungeon_settings"):
                acc["dungeon_settings"] = account_data["dungeon_settings"].copy()
            else:
                acc["dungeon_settings"] = []
            # Add duel dungeon settings if present
            if account_data.get("duel_dungeon_settings"):
                acc["duel_dungeon_settings"] = account_data["duel_dungeon_settings"].copy()
            else:
                acc["duel_dungeon_settings"] = []
            result.append(acc)
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting player accounts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get player accounts: {str(e)}")

def toggle_user_status(player_email: str, data: dict = Body(...), current_user: str = Depends(verify_token)):
    """Enable or disable a user (admin only)"""
    try:
        # Check if current user is admin
        try:
            admin_entity = users_table.get_entity(partition_key=current_user, row_key='0')
            if admin_entity.get('user_type', 'player') != 'admin':
                raise HTTPException(status_code=403, detail="Admin access required")
        except Exception:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Get player entity
        try:
            player_entity = users_table.get_entity(partition_key=player_email, row_key='0')
        except Exception:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get disabled status from request body
        disabled = data.get('disabled', False)
        
        # Update disabled status
        player_entity['disabled'] = disabled
        users_table.upsert_entity(player_entity)
        
        action = "disabled" if disabled else "enabled"
        return {
            "success": True,
            "message": f"User {player_email} has been {action}",
            "disabled": disabled
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling user status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to toggle user status: {str(e)}")

async def extract_cookies_interactive(req: ExtractCookiesInteractiveRequest, current_user: str = Depends(verify_token)):
    """
    Interactive cookie extraction - opens a browser for user to log in manually,
    then extracts cookies after login is detected.
    Note: This requires a display/GUI environment and may not work in headless servers.
    """
    try:
        from cookie_extractor import extract_cookies_interactive as extract_interactive_async
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        # Normalize the URL - add http:// if missing
        normalized_page_url = normalize_url(req.page_url)
        
        def run_playwright():
            """Run Playwright in a separate thread with its own event loop"""
            # Set event loop policy for Windows subprocess support
            import sys
            if sys.platform == 'win32':
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(extract_interactive_async(
                    page_url=normalized_page_url,
                    timeout=req.timeout or 300
                ))
            finally:
                loop.close()
        
        # Run Playwright in a thread pool executor to avoid event loop conflicts
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, run_playwright)
        
        if result['success']:
            return {
                "success": True,
                "cookie_string": result['cookie_string'],
                "weeCookie": result['weeCookie'],
                "50hero_session": result['50hero_session'],
                "message": "Cookies extracted successfully"
            }
        else:
            raise HTTPException(status_code=400, detail=f"Failed to extract cookies: {result.get('error', 'Unknown error')}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in interactive cookie extraction: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to extract cookies: {str(e)}")

async def open_browser_with_cookies(req: OpenBrowserWithCookiesRequest, current_user: str = Depends(verify_token)):
    """
    Open a browser page to login to a game account using stored cookies (admin only).
    This is similar to making a request to home with cookies, but opens a browser window.
    """
    try:
        # Check if current user is admin
        _check_admin_access(current_user)
        
        # Get the account's stored cookies
        cached_account = get_cached_account(req.target_username, req.account_name)
        if not cached_account:
            # Get all cached accounts for debugging
            all_accounts = get_cached_accounts(req.target_username)
            available_accounts = list(all_accounts.keys())
            logger.warning(f"Account '{req.account_name}' not found for user '{req.target_username}'. Available accounts: {available_accounts}")
            raise HTTPException(status_code=404, detail=f"Account '{req.account_name}' not found. Available accounts: {available_accounts}")
        
        cookie_string = cached_account["cookie"]
        
        from cookie_extractor import open_browser_with_cookies as open_browser_async
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        # Normalize the URL - add http:// if missing
        normalized_game_url = normalize_url(req.game_url)
        
        def run_playwright():
            """Run Playwright in a separate thread with its own event loop"""
            # Set event loop policy for Windows subprocess support
            import sys
            if sys.platform == 'win32':
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(open_browser_async(
                    cookie_string=cookie_string,
                    game_url=normalized_game_url
                ))
            finally:
                loop.close()
        
        # Run Playwright in a thread pool executor to avoid event loop conflicts
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, run_playwright)
        
        if result['success']:
            return {
                "success": True,
                "message": f"Browser opened successfully for account {req.account_name}",
                "url": result.get('url')
            }
        else:
            raise HTTPException(status_code=400, detail=f"Failed to open browser: {result.get('error', 'Unknown error')}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error opening browser with cookies: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to open browser: {str(e)}")

def _check_admin_access(current_user: str):
    """Helper function to check if current user is admin"""
    try:
        admin_entity = users_table.get_entity(partition_key=current_user, row_key='0')
        if admin_entity.get('user_type', 'player') != 'admin':
            raise HTTPException(status_code=403, detail="Admin access required")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=403, detail="Admin access required")

def get_job_status(current_user: str = Depends(verify_token)):
    """Get current job execution status (admin only)"""
    try:
        _check_admin_access(current_user)
        
        from job_execution_tracker import get_recent_executions
        
        # Get active jobs from in-memory tracking
        active_jobs_list = []
        if active_jobs_lock and active_jobs is not None:
            import time
            with active_jobs_lock:
                for execution_id, job_info in active_jobs.items():
                    duration = time.time() - job_info.get('start_time', time.time())
                    active_jobs_list.append({
                        "execution_id": execution_id,
                        "username": job_info.get('username'),
                        "job_id": job_info.get('job_id'),
                        "start_time": datetime.fromtimestamp(job_info.get('start_time', time.time())).isoformat(),
                        "duration_seconds": int(duration)
                    })
        
        # Get recent executions from DB
        recent_executions = get_recent_executions(limit=50)
        recent_list = []
        for entity in recent_executions:
            recent_list.append({
                "execution_id": entity.get('RowKey'),
                "username": entity.get('PartitionKey'),
                "job_id": entity.get('job_id'),
                "job_type": entity.get('job_type'),
                "status": entity.get('status'),
                "scheduled_time": entity.get('scheduled_time'),
                "execution_start_time": entity.get('execution_start_time'),
                "execution_end_time": entity.get('execution_end_time'),
                "error_message": entity.get('error_message')
            })
        
        # Get shutdown status
        shutdown_status = False
        paused_status = False
        if shutdown_requested:
            shutdown_status = shutdown_requested.is_set()
        if scheduler_paused_lock:
            with scheduler_paused_lock:
                paused_status = scheduler_paused
        
        return {
            "success": True,
            "shutdown_requested": shutdown_status,
            "scheduler_paused": paused_status,
            "active_jobs_count": len(active_jobs_list),
            "active_jobs": active_jobs_list,
            "recent_executions": recent_list
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {str(e)}")

def initiate_shutdown(current_user: str = Depends(verify_token)):
    """Initiate graceful shutdown (admin only)"""
    try:
        _check_admin_access(current_user)
        
        if shutdown_requested is None or scheduler_paused_lock is None:
            raise HTTPException(status_code=500, detail="Shutdown system not initialized")
        
        # Check if already shutting down
        if shutdown_requested.is_set():
            active_count = 0
            if active_jobs_lock and active_jobs is not None:
                with active_jobs_lock:
                    active_count = len(active_jobs)
            return {
                "success": True,
                "message": "Shutdown already in progress",
                "active_jobs_count": active_count
            }
        
        # Set shutdown flags
        shutdown_requested.set()
        if scheduler_paused_lock:
            with scheduler_paused_lock:
                # Modify the scheduler_paused flag in main.py module
                import sys
                main_module = sys.modules.get('main')
                if main_module:
                    main_module.scheduler_paused = True
                # Also update local reference
                global scheduler_paused
                scheduler_paused = True
        
        # Count active jobs
        active_count = 0
        if active_jobs_lock and active_jobs is not None:
            with active_jobs_lock:
                active_count = len(active_jobs)
        
        logger.info(f"Admin {current_user} initiated graceful shutdown. Active jobs: {active_count}")
        
        return {
            "success": True,
            "message": "Shutdown initiated. Waiting for jobs to complete...",
            "active_jobs_count": active_count,
            "scheduler_paused": True
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating shutdown: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to initiate shutdown: {str(e)}")

def get_shutdown_status(current_user: str = Depends(verify_token)):
    """Get current shutdown status (admin only)"""
    try:
        _check_admin_access(current_user)
        
        shutdown_status = False
        paused_status = False
        active_count = 0
        
        if shutdown_requested:
            shutdown_status = shutdown_requested.is_set()
        if scheduler_paused_lock:
            with scheduler_paused_lock:
                paused_status = scheduler_paused
        if active_jobs_lock and active_jobs is not None:
            with active_jobs_lock:
                active_count = len(active_jobs)
        
        # Determine if safe to restart
        safe_to_restart = shutdown_status and paused_status and active_count == 0
        
        return {
            "success": True,
            "shutdown_requested": shutdown_status,
            "scheduler_paused": paused_status,
            "active_jobs_count": active_count,
            "safe_to_restart": safe_to_restart,
            "message": "Safe to restart" if safe_to_restart else f"Waiting for {active_count} jobs to complete"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting shutdown status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get shutdown status: {str(e)}")