import threading
import time
import queue
from datetime import datetime
from fastapi import HTTPException, Depends
from fastapi.responses import StreamingResponse

from pvehall import PVEHall
from character import Character
from log import get_user_logger, get_user_stream_handler, setup_logging
from cache_utils import get_cached_accounts
from request_utils import is_request_active, mark_request_active, clear_requests_for_user, mark_request_inactive
from models import HallCombatStreamRequest
from auth_utils import verify_token
# Setup logging
logger = setup_logging()

# Global variables that will be set by main.py
hall_combat_threads = None
hall_combat_lock = None
running_halls = None
hall_stop_events = None
user_stop_signals = None
default_hall_setting = None
users_table = None

def set_hall_globals(threads_dict, lock_obj, halls_dict, stop_events_dict, stop_signals_dict, default_settings, users_table_client=None):
    """Set the global hall variables from main.py"""
    global hall_combat_threads, hall_combat_lock, running_halls, hall_stop_events, user_stop_signals, default_hall_setting, users_table
    hall_combat_threads = threads_dict
    hall_combat_lock = lock_obj
    running_halls = halls_dict
    hall_stop_events = stop_events_dict
    user_stop_signals = stop_signals_dict
    default_hall_setting = default_settings
    if users_table_client:
        users_table = users_table_client

def is_hall_combat_running(username: str) -> bool:
    """Check if hall combat is running for a user"""
    if hall_combat_lock is None:
        return False
    with hall_combat_lock:
        if username not in hall_combat_threads:
            return False
        
        thread_info = hall_combat_threads[username]
        active_count = thread_info.get('active_count', 0)
        
        # If no active threads, clean up the stale entry
        if active_count <= 0:
            del hall_combat_threads[username]
            # Clear any active requests for this user when cleaning up stale entry
            clear_requests_for_user(username)
            return False
        
        return True

def get_hall_combat_streaming_handler(username: str):
    """Get or create streaming handler for hall combat"""
    from log import user_log_manager
    return user_log_manager.get_streaming_handler(username)

def register_hall_combat_threads(username: str, threads: list, streaming_handler):
    """Register hall combat threads for cleanup"""
    if hall_combat_lock is None:
        return
    with hall_combat_lock:
        hall_combat_threads[username] = {
            'threads': threads,
            'streaming_handler': streaming_handler,
            'start_time': datetime.now()
        }

def cleanup_all_threads():
    """Clean up all threads"""
    if hall_combat_lock is None:
        return
    with hall_combat_lock:
        for (username, thread_name), thread in threading.enumerate():
            if hasattr(thread, 'is_alive') and thread.is_alive():
                thread.join(timeout=1)
        hall_combat_threads.clear()

def cleanup_stale_combat_sessions():
    """Clean up stale combat session entries with no active threads"""
    if hall_combat_lock is None:
        return
    
    with hall_combat_lock:
        stale_users = []
        for username, thread_info in hall_combat_threads.items():
            active_count = thread_info.get('active_count', 0)
            if active_count <= 0:
                stale_users.append(username)
        
        for username in stale_users:
            del hall_combat_threads[username]
            logger.info(f"Cleaned up stale combat session for user: {username}")
            # Clear any active requests for this user when cleaning up stale session
            clear_requests_for_user(username)
        
        if stale_users:
            logger.info(f"Cleaned up {len(stale_users)} stale combat sessions")

def _setup_hall_combat_session(username: str, account_names: list, session_type: str, skip_combat_count_check: bool = False):
    """Common setup logic for hall combat sessions"""
    # Check if there's already an active request for this user and accounts
    if is_request_active(username, session_type, account_names):
        logger.warning(f"Duplicate request detected for user {username} with accounts {account_names}")
        raise HTTPException(status_code=409, detail=f"A {session_type} session is already running for these accounts. Please wait for it to complete or stop it first.")
    
    # Mark this request as active
    if not mark_request_active(username, session_type, account_names):
        logger.error(f"Failed to mark request as active for user {username}")
        raise HTTPException(status_code=500, detail=f"Failed to start {session_type} session")
    
    # Use cached accounts instead of database query
    selected_accs = []
    cached_accounts = get_cached_accounts(username)
    for acc_name in account_names:
        cached_account = cached_accounts.get(acc_name)
        if not cached_account:
            raise HTTPException(status_code=404, detail=f"Account {acc_name} not found")

        # Check combat counts - skip if already completed weekly quota (only when called from backend job)
        if not skip_combat_count_check:
            combat_counts = cached_account.get("combat_counts")
            if combat_counts is not None:
                try:
                    # Parse combat counts format "100/100"
                    current_count, total_count = map(int, combat_counts.split('/'))
                    if current_count >= total_count and current_count != 0:
                        logger.info(f"Skipping hall challenge for {acc_name}: already completed weekly quota ({combat_counts})")
                        continue
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Invalid combat_counts format for {acc_name}: {combat_counts}, error: {e}")
                    # Continue with challenge if format is invalid
        
        # Convert cached account back to entity format for backward compatibility
        entity = cached_account.copy()
        # Add the account name to the entity (cached accounts don't have this field)
        entity['name'] = acc_name
        
        # Convert hall_settings JSON string back to individual fields for PVEHall compatibility
        hall_settings = cached_account["hall_settings"]
        if hall_settings:
            # Add individual hall fields to entity
            for field, value in hall_settings.items():
                entity[field] = value
            # Remove the hall_settings field since PVEHall expects individual fields
            if "hall_settings" in entity:
                del entity["hall_settings"]
        
        selected_accs.append(entity)
    
    if not selected_accs:
        # All accounts have completed their weekly quota or no valid accounts found
        # Mark request as inactive before raising exception
        mark_request_inactive(username, session_type, account_names)
        
        if any(cached_accounts.get(acc_name) for acc_name in account_names):
            raise HTTPException(status_code=400, detail="All selected accounts have completed their weekly combat quota")
        else:
            raise HTTPException(status_code=404, detail="No valid accounts found")
    
    # Get user-specific logger and streaming handler
    user_logger = get_user_logger(username)
    streaming_handler = get_hall_combat_streaming_handler(username)
    
    return selected_accs, user_logger, streaming_handler

def _create_hall_instances(selected_accs, username, user_logger):
    """Create hall instances for the selected accounts"""
    halls = []
    for entity in selected_accs:
        acc_name = entity['name']
        cookie = entity['cookie']
        try:
            character = Character(username, acc_name, cookie, user_logger)
            hall = PVEHall(character, entity, user_logger)
            halls.append((acc_name, hall))
        except Exception as e:
            logger.error(f"Failed to create hall for {acc_name}: {e}")
            halls.append(None)
    return halls

def _create_streaming_response(event_stream_func, username, account_names, session_type):
    """Create streaming response with proper headers"""
    return StreamingResponse(
        event_stream_func(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Keep-Alive": "timeout=300, max=1000",  # Keep connection alive for 5 minutes
            "Transfer-Encoding": "chunked",  # Explicitly set chunked encoding
        }
    )

def stop_combat_for_user(username: str) -> dict:
    """Stop combat for a specific user"""
    logger.info(f"Stop combat requested for user: {username}")
    
    # Set global stop signal first
    user_stop_signals[username] = True
    
    # Get halls for this user
    halls = running_halls.get(username, [])
    
    # Check for active threads by name
    active_threads = []
    for thread in threading.enumerate():
        if thread.is_alive() and thread.name and username in thread.name:
            # Check if it's a combat-related thread
            if any(keyword in thread.name.lower() for keyword in ['hall_combat', 'hall_challenge']):
                active_threads.append(thread)
    
    # If we have halls or active threads, proceed with stopping
    if halls or active_threads:
        stopped_count = 0
        
        # Step 1: Set _stopped = True on all PVEHall objects
        logger.info(f"Setting _stopped=True on {len(halls)} PVEHall objects for user {username}")
        for hall in halls:
            try:
                if hall is not None:
                    hall._stopped = True
                    stopped_count += 1
                    logger.info(f"Set _stopped=True on hall for user {username}")
            except Exception as e:
                logger.error(f"Error setting _stopped on hall for user {username}: {e}")
        
        # Step 2: Wait for threads to finish naturally
        logger.info(f"Waiting for {len(active_threads)} threads to finish naturally for user {username}")
        wait_time = 0
        max_wait = 40  # Wait up to 10 seconds for natural completion
        
        while wait_time < max_wait:
            # Check if threads are still alive
            alive_threads = [t for t in active_threads if t.is_alive()]
            
            if not alive_threads:
                logger.info(f"All threads finished for user {username}")
                break
            
            logger.info(f"Waiting for {len(alive_threads)} threads to finish... {wait_time:.1f}s elapsed")
            time.sleep(2)
            wait_time += 2
        
        if wait_time >= max_wait:
            logger.warning(f"Some threads still alive after {max_wait}s for user {username}, but allowing natural completion")
        
        # Step 3: Clean up tracking data (threads should have cleaned themselves up)
        logger.info(f"Cleaning up tracking data for user {username}")
        
        # Clear the running halls list for this user
        running_halls[username] = []
        
        # Clear any stop events for this user
        for key in list(hall_stop_events.keys()):
            if key[0] == username:
                del hall_stop_events[key]
        
        clear_requests_for_user(username)
        
        # Clear the global stop signal for this user
        if username in user_stop_signals:
            del user_stop_signals[username]
        
        # Clear streaming queue to prevent stale messages
        try:
            streaming_handler = get_user_stream_handler(username)
            if streaming_handler:
                cleared_count = 0
                while not streaming_handler.log_queue.empty():
                    try:
                        streaming_handler.log_queue.get_nowait()
                        cleared_count += 1
                    except queue.Empty:
                        break
                logger.info(f"Cleared {cleared_count} messages from streaming queue for user {username}")
        except Exception as e:
            logger.error(f"Error clearing streaming queue for user {username}: {e}")
        
        # Clear all active requests for this user to prevent stale session state
        try:
            clear_requests_for_user(username)
            logger.info(f"Cleared all active requests for user {username}")
        except Exception as e:
            logger.error(f"Error clearing active requests for user {username}: {e}")
        
        # Create success message
        message = f"Combat stopped for {stopped_count} halls, {len(active_threads)} threads"
        logger.info(f"Stop combat completed for user {username}: {message}")
        return {"success": True, "message": message}
    else:
        # Even if no actual combat is running, clear any stale request tracking entries
        # This handles the case where the frontend thinks there's an active session
        # but the backend has no actual combat running
        try:
            clear_requests_for_user(username)
            logger.info(f"Cleared stale active requests for user {username}")
        except Exception as e:
            logger.error(f"Error clearing stale active requests for user {username}: {e}")
        
        logger.info(f"No running combat found for user {username}")
        return {"success": False, "message": "No running combat found"}


def hall_combat_stream(req: HallCombatStreamRequest, current_user: str = Depends(verify_token)):
    """Hall combat streaming endpoint - supports both full combat and individual hall challenge"""
    # Check if admin is accessing on behalf of another user
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
    
    account_names = None
    hall_name = req.hall_name  # Optional: if provided, only challenge this specific hall
    
    # Determine session type based on whether hall_name is provided
    session_type = "hall_challenge" if hall_name else "hall_combat_stream"
    
    try:
        # Handle both single and multiple account requests
        # Convert account_names to list if it's a single string
        if isinstance(req.account_names, str):
            account_names = [req.account_names]
        else:
            account_names = req.account_names
        
        # Ensure account_names is set before any cleanup operations
        if not account_names:
            raise HTTPException(status_code=400, detail="account_names is required")
        
        # Check if hall_combat_stream is already running for this user
        if is_hall_combat_running(username):
            # Stop existing session first to start a new one
            stop_combat_for_user(username)
        
        # Clear any stale active requests for this user/account combination before starting new session
        # This ensures we don't have leftover state from previous requests
        if is_request_active(username, session_type, account_names):
            logger.warning(f"Found stale active request for {username} with accounts {account_names}, clearing it")
            mark_request_inactive(username, session_type, account_names)
        
        # Use common setup logic
        # Skip combat count check when called from UI (skip_combat_count_check=True, default), 
        # but check when called from backend jobs (skip_combat_count_check=False)
        skip_check = req.skip_combat_count_check
        try:
            selected_accs, user_logger, streaming_handler = _setup_hall_combat_session(username, account_names, session_type, skip_combat_count_check=skip_check)
        except HTTPException as e:
            if e.status_code == 400 and "weekly combat quota" in str(e.detail):
                # Handle case where all accounts have completed their weekly quota
                def quota_completed_stream():
                    yield f"data: 所选账号已完成本周挑战次数，无需进行幻境挑战\n\n"
                    yield f"data: 流式传输完成\n\n"
                return StreamingResponse(quota_completed_stream(), media_type="text/plain")
            else:
                raise
        
        # If hall_name is provided, filter the hall config to only include the target hall
        if hall_name:
            hall_fields = ["封神异志", "平倭群英传", "武林群侠传", "三国鼎立", "乱世群雄", "绝代风华"]
            for acc in selected_accs:
                # Save the original setting for the target hall
                original_setting = acc.get(hall_name, "")
                # Remove all other hall settings (delete them completely instead of setting to "")
                for field_name in hall_fields:
                    if field_name != hall_name and field_name in acc:
                        del acc[field_name]
                # Ensure the target hall has its original setting
                if hall_name not in acc:
                    acc[hall_name] = original_setting
        
        # Create hall instances and run combat
        halls = _create_hall_instances(selected_accs, username, user_logger)
        threads = []

        def run_hall(hall_tuple, acc_name, user_name, logger, target_hall=None):
            try:
                acc_name_from_tuple, hall = hall_tuple
                if target_hall:
                    logger.info(f'{acc_name}开始挑战幻境 {target_hall}')
                else:
                    logger.info(f'{acc_name}开始幻境挑战')
                
                # Add hall to running_halls for stop tracking
                if user_name not in running_halls:
                    running_halls[user_name] = []
                running_halls[user_name].append(hall)
                
                hall._set_thread(threading.current_thread())
                hall.run()
            except Exception as e:
                error_msg = str(e)
                if 'gzip' in error_msg.lower() or 'decompress' in error_msg.lower():
                    logger.error(f'{acc_name}幻境挑战出错: Gzip解压错误 - {e}')
                else:
                    logger.error(f'{acc_name}幻境挑战出错: {e}')
            finally:
                hall._clear_thread()
                
                # Decrement the thread counter and check if all threads are done
                with hall_combat_lock:
                    if user_name in hall_combat_threads:
                        thread_info = hall_combat_threads[user_name]
                        if 'active_count' not in thread_info:
                            thread_info['active_count'] = len(thread_info['threads'])
                        
                        thread_info['active_count'] -= 1
                        
                        if thread_info['active_count'] <= 0:
                            del hall_combat_threads[username]
                            user_logger.info(f'{user_name} 所有幻境挑战结束, 清除线程引用')
                            # Mark request as inactive when all threads complete
                            mark_request_inactive(username, session_type, account_names)

        # Start threads for each hall
        for i, (entity, hall_tuple) in enumerate(zip(selected_accs, halls)):
            if hall_tuple:
                acc_name, hall = hall_tuple
                thread_name = f"hall_challenge_{username}_{acc_name}_{i}" if hall_name else f"hall_combat_{username}_{acc_name}_{i}"
                t = threading.Thread(
                    target=run_hall, 
                    args=(hall_tuple, acc_name, username, user_logger, hall_name),
                    name=thread_name,
                    daemon=True
                )
                threads.append(t)
                t.start()
        
        # Register threads and streaming handler globally
        register_hall_combat_threads(username, threads, streaming_handler)

        def event_stream():
            try:
                if hall_name:
                    yield f"data: 连接已建立，开始挑战 {hall_name}...\n\n"
                else:
                    yield "data: 连接已建立，开始流式传输...\n\n"
                
                def is_alive():
                    return any(t is not None and hasattr(t, 'is_alive') and t.is_alive() for t in threads)
                
                last_heartbeat = time.time()
                heartbeat_interval = 15.0
                
                while is_alive() or not streaming_handler.log_queue.empty():
                    try:
                        time_since_heartbeat = time.time() - last_heartbeat
                        timeout = max(1.0, heartbeat_interval - time_since_heartbeat)
                        
                        msg = streaming_handler.log_queue.get(timeout=timeout)
                        yield f"data: {msg}\n\n"
                        
                        last_heartbeat = time.time()
                        
                    except queue.Empty:
                        current_time = time.time()
                        if current_time - last_heartbeat >= heartbeat_interval:
                            yield "data: [心跳] 连接保持活跃...\n\n"
                            last_heartbeat = current_time
                        continue
                
                # Clean up halls
                for hall_tuple in halls:
                    if hall_tuple is None:
                        continue
                    try:
                        acc_name, hall = hall_tuple
                        if username in running_halls and hall in running_halls[username]:
                            running_halls[username].remove(hall)                           
                    except Exception as hall_cleanup_error:
                        pass
                
                yield f"data: 流式传输完成\n\n"
                
            except Exception as e:
                yield f"data: 流式传输错误: {str(e)}\n\n"
            finally:
                # Mark request as inactive when stream completes
                mark_request_inactive(username, session_type, account_names)

        user_logger.info('########################################################################################')
            
        response = _create_streaming_response(event_stream, username, account_names, session_type)
        
        # Add cleanup when response is closed
        def cleanup_on_close():
            mark_request_inactive(username, session_type, account_names)
        
        # Note: We can't directly hook into the response close event in FastAPI
        # The cleanup will happen in the event_stream function when it completes
        
        return response
        
    except HTTPException:
        # Mark request as inactive on error (only if account_names is set)
        if account_names is not None:
            try:
                mark_request_inactive(username, session_type, account_names)
            except Exception as cleanup_error:
                logger.warning(f"Error cleaning up request on HTTPException: {cleanup_error}")
        raise
    except Exception as e:
        # Mark request as inactive on error (only if account_names is set)
        if account_names is not None:
            try:
                mark_request_inactive(username, session_type, account_names)
            except Exception as cleanup_error:
                logger.warning(f"Error cleaning up request on Exception: {cleanup_error}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

def resume_stream(req: HallCombatStreamRequest, current_user: str = Depends(verify_token)):
    """Resume an existing hall combat stream"""
    # Check if admin is accessing on behalf of another user
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
    
    # Handle both single and multiple account requests
    # Convert account_names to list if it's a single string
    if isinstance(req.account_names, str):
        account_names = [req.account_names]
    else:
        account_names = req.account_names
    
    # Determine session type - check for hall_challenge first, then fall back to hall_combat_stream
    session_type = "hall_challenge" if is_request_active(username, "hall_challenge", account_names) else "hall_combat_stream"
    
    try:
        # Get user logger for error handling
        user_logger = get_user_logger(username)
        # Check if there's an active combat session for this user and accounts
        # Check both hall_combat_stream and hall_challenge session types
        has_active_session = (is_request_active(username, "hall_combat_stream", account_names) or 
                              is_request_active(username, "hall_challenge", account_names))
        
        if has_active_session:
            # Get streaming handler for active session
            streaming_handler = get_hall_combat_streaming_handler(username)
            
            if not streaming_handler:
                raise HTTPException(status_code=500, detail="Failed to get user streaming handler")
            
            def resume_event_stream():
                try:
                    yield "data: 重新连接成功，继续流式传输...\n\n"
                    
                    # Clear any stale messages from the queue to prevent partial log issues
                    stale_messages = []
                    while not streaming_handler.log_queue.empty():
                        try:
                            msg = streaming_handler.log_queue.get_nowait()
                            stale_messages.append(msg)
                        except queue.Empty:
                            break
                    
                    # If there are stale messages, send them first
                    if stale_messages:
                        yield f"data: [重连] 发送缓存的消息 ({len(stale_messages)} 条)...\n\n"
                        for msg in stale_messages:
                            yield f"data: {msg}\n\n"
                    
                    # Continue streaming from the existing log queue
                    while not streaming_handler.log_queue.empty():
                        try:
                            msg = streaming_handler.log_queue.get(timeout=1.0)
                            yield f"data: {msg}\n\n"
                        except queue.Empty:
                            break
                    
                    # Send heartbeat to indicate connection is alive
                    yield "data: [重连] 流式传输已恢复\n\n"
                    
                except Exception as e:
                    user_logger.error(f'Error in resume event stream: {e}')
                    yield f"data: 重连流式传输错误: {str(e)}\n\n"
            
            return StreamingResponse(
                resume_event_stream(), 
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                    "Keep-Alive": "timeout=300, max=1000",
                    "Transfer-Encoding": "chunked",
                }
            )
        else:
            # No active session, fall back to loading the latest log file
            # user_logger.info(f"没有找到活跃的幻境挑战，加载最新日志文件")
            
            # Get the latest log file for the user
            from log import user_log_manager
            log_file_path = user_log_manager.get_latest_log_file(username)
            if not log_file_path:
                user_logger.error(f"No log files found for user: {username}")
                raise HTTPException(status_code=404, detail="No active combat session found and no log files available")
            
            def log_stream():
                try:
                    # Try to read the file with retry logic for file locking issues
                    max_retries = 3
                    retry_delay = 0.1  # 100ms
                    
                    for attempt in range(max_retries):
                        try:
                            with open(log_file_path, 'r', encoding='utf-8') as f:
                                # Read and send the file content
                                content = f.read()
                                if content.strip():
                                    yield f"data: [历史日志] 加载最新日志文件...\n\n"
                                    for line in content.strip().split('\n'):
                                        if line.strip():
                                            yield f"data: {line}\n\n"
                                else:
                                    yield f"data: [历史日志] 日志文件为空\n\n"
                            break
                        except (IOError, OSError) as e:
                            if attempt < max_retries - 1:
                                user_logger.warning(f"Failed to read log file (attempt {attempt + 1}), retrying in {retry_delay}s: {e}")
                                time.sleep(retry_delay)
                                retry_delay *= 2
                            else:
                                user_logger.error(f"Failed to read log file after {max_retries} attempts: {e}")
                                yield f"data: 无法读取日志文件: {str(e)}\n\n"
                                return
                    
                    yield f"data: [历史日志] 日志加载完成\n\n"
                    
                except Exception as e:
                    user_logger.error(f'Error in log stream: {e}')
                    yield f"data: 日志流式传输错误: {str(e)}\n\n"
            
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
            
    except HTTPException:
        # Mark request as inactive on error
        mark_request_inactive(username, session_type, account_names)
        raise
    except Exception as e:
        # Mark request as inactive on error
        mark_request_inactive(username, session_type, account_names)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

def auto_challenge(username: str, account_names: list = None):
    """Auto challenge for a user"""
    if account_names is None or len(account_names) == 0:
        # If no accounts specified, get all accounts for the user
        cached_accounts = get_cached_accounts(username)
        account_names = list(cached_accounts.keys())
    
    if account_names:
        # Backend jobs should check combat counts, so set skip_combat_count_check=False
        hall_combat_stream(HallCombatStreamRequest(account_names=account_names, skip_combat_count_check=False), current_user=username)
        logger.info(f"Auto challenge for user {username}, accounts: {account_names}")
