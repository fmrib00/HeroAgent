import json
import threading
from datetime import datetime, timezone
from log import setup_logging
from validation_utils import escape_for_azure_table_query

# Setup logging
logger = setup_logging()

# Thread-safe global accounts cache
# Structure: {username: {account_name: {cookie, hall_settings, ...}}}
accounts_cache = {}
accounts_cache_lock = threading.RLock()

# Thread-safe global user settings cache
# Structure: {username: {job_settings: str, ...}}
user_settings_cache = {}
user_settings_cache_lock = threading.RLock()

# Global variables that will be set by main.py
heroaccounts_table = None
users_table = None

def set_table_clients(heroaccounts_table_client, users_table_client):
    """Set the table clients from main.py"""
    global heroaccounts_table, users_table
    heroaccounts_table = heroaccounts_table_client
    users_table = users_table_client

def update_account_combat_counts(username: str, account_name: str, combat_count: int, total_combat_count: int):
    """Update combat counts for an account after hall challenge completion"""
    try:
        # Get the current entity
        entity = heroaccounts_table.get_entity(partition_key=username, row_key=account_name)
        
        # Update combat_counts field
        entity["combat_counts"] = f"{combat_count}/{total_combat_count}"
        
        # Save back to database
        heroaccounts_table.upsert_entity(entity)
        
        # Invalidate cache for this user
        invalidate_user_cache(username)
        
        logger.info(f"Updated combat counts for {username}/{account_name}: {entity['combat_counts']}")
        
    except Exception as e:
        logger.error(f"Failed to update combat counts for {username}/{account_name}: {e}")

def reset_all_combat_counts(username: str):
    """Reset combat_counts field to None for all accounts (daily reset)"""
    try:
        cached_accounts = get_cached_accounts(username)
        reset_count = 0
        for account_name, account_data in cached_accounts.items():
            try:
                # Only reset if combat_counts is not None
                current_combat_counts = account_data.get("combat_counts")
                if current_combat_counts is not None:
                    # Get the full entity from the database
                    entity = heroaccounts_table.get_entity(partition_key=username, row_key=account_name)
                    
                    # Update combat_counts field
                    entity["combat_counts"] = "0/0"  # Use "0" as reset marker
                    
                    # Save back to database
                    heroaccounts_table.upsert_entity(entity)
                    reset_count += 1
            except Exception as e:
                logger.error(f"Failed to reset combat counts for {username}/{account_name}: {e}")
        
        # Force refresh cache for the user to ensure fresh data
        refresh_user_cache(username)
        
        logger.info(f"Combat counts reset completed for user {username}. Reset {reset_count} accounts.")
        
    except Exception as e:
        logger.error(f"Failed to reset combat counts for user {username}: {e}")

def get_cached_accounts(username: str):
    """Get cached accounts for a user"""
    with accounts_cache_lock:
        if username not in accounts_cache:
            refresh_user_cache(username)
        return accounts_cache.get(username, {})

def get_cached_account(username: str, account_name: str):
    """Get a specific cached account"""
    accounts = get_cached_accounts(username)
    return accounts.get(account_name)

def update_duel_cookies(username: str, account_name: str, duel_cookies: str):
    """Update duel cookies for a specific account in cache"""
    with accounts_cache_lock:
        if username in accounts_cache and account_name in accounts_cache[username]:
            accounts_cache[username][account_name]['duel_cookies'] = duel_cookies
            logger.debug(f"Updated duel cookies for {username}/{account_name}")

def invalidate_user_cache(username: str):
    """Invalidate cache for a specific user"""
    with accounts_cache_lock:
        if username in accounts_cache:
            del accounts_cache[username]

def invalidate_all_cache():
    """Invalidate all accounts cache"""
    with accounts_cache_lock:
        accounts_cache.clear()

def refresh_user_cache(username: str):
    """Refresh cache for a specific user"""
    try:
        if heroaccounts_table is None:
            logger.warning(f"refresh_user_cache: heroaccounts_table is None for username={username}")
            return

        # Escape username for Azure Table query to prevent injection
        escaped_username = escape_for_azure_table_query(username)
        filter_query = f"PartitionKey eq '{escaped_username}'"
        
        entities = heroaccounts_table.query_entities(query_filter=filter_query)
        entities_list = list(entities)
        accounts = {}
        
        # Preserve existing duel_cookies if cache exists
        existing_duel_cookies = {}
        with accounts_cache_lock:
            if username in accounts_cache:
                for account_name, account_data in accounts_cache[username].items():
                    if account_data.get('duel_cookies'):
                        existing_duel_cookies[account_name] = account_data['duel_cookies']
        
        # Process entities (only those with matching PartitionKey)
        for entity in entities_list:
            account_name = entity['RowKey']
            accounts[account_name] = {
                'cookie': entity.get('cookie', ''),
                'hall_settings': json.loads(entity.get('hall_settings', '{}')),
                'common_settings': json.loads(entity.get('common_settings', '{}')),
                'dungeon_settings': json.loads(entity.get('dungeon_settings', '[]')),
                'duel_dungeon_settings': json.loads(entity.get('duel_dungeon_settings', '[]')),
                'combat_counts': entity.get('combat_counts'),
                'last_updated': entity.get('last_updated'),
                'duel_cookies': existing_duel_cookies.get(account_name)  # Preserve existing duel cookies
            }
        
        with accounts_cache_lock:
            accounts_cache[username] = accounts
            
        logger.info(f"Refreshed cache for user {username}: {len(accounts)} accounts")
        
    except Exception as e:
        logger.error(f"Failed to refresh cache for user {username}: {e}")

def get_cached_user_settings(username: str):
    """Get cached user settings for a user"""
    with user_settings_cache_lock:
        if username not in user_settings_cache:
            refresh_user_settings_cache(username)
        return user_settings_cache.get(username, {})

def invalidate_user_settings_cache(username: str):
    """Invalidate user settings cache for a specific user"""
    with user_settings_cache_lock:
        if username in user_settings_cache:
            del user_settings_cache[username]

def invalidate_all_user_settings_cache():
    """Invalidate all user settings cache"""
    with user_settings_cache_lock:
        user_settings_cache.clear()

def get_default_job_settings():
    """Get default job settings for users when job_settings is null"""
    return {
        'auto_challenge': {
            'type': 'daily',
            'enabled': True,
            'hour': '2',
            'minute': '0',
            'account_names': []
        },
        'capture_slave': {
            'type': 'hourly',
            'enabled': True,
            'minute': '50',
            'account_names': []
        },
        'wuguan': {
            'type': 'hourly',
            'enabled': True,
            'minute': '55',
            'account_names': []
        },
        'morning_routine': {
            'type': 'daily',
            'enabled': True,
            'hour': '10',
            'minute': '0',
            'account_names': []
        },
        'night_routine': {
            'type': 'daily',
            'enabled': True,
            'hour': '21',
            'minute': '0',
            'account_names': []
        },
        'fengyun': {
            'type': 'daily',
            'enabled': True,
            'hour': '12',
            'minute': '0',
            'account_names': []
        },
        'dungeon_and_monster': {
            'type': 'daily',
            'enabled': True,
            'hour': '17',
            'minute': '0',
            'account_names': []
        },
        'monday_routine': {
            'type': 'weekly',
            'enabled': True,
            'day_of_week': '0',  # Monday is 0 in Python datetime
            'hour': '9',
            'minute': '0',
            'account_names': []
        },
        'wednesday_routine': {
            'type': 'weekly',
            'enabled': True,
            'day_of_week': '2',  # Wednesday is 2 in Python datetime
            'hour': '11',
            'minute': '0',
            'account_names': []
        },
        'saturday_routine': {
            'type': 'weekly',
            'enabled': True,
            'day_of_week': '5',  # Saturday is 5 in Python datetime
            'hour': '11',
            'minute': '0',
            'account_names': []
        }
    }

def refresh_user_settings_cache(username: str):
    """Refresh user settings cache for a specific user"""
    try:
        if users_table is None:
            return
            
        entity = None
        try:
            entity = users_table.get_entity(partition_key=username, row_key='0')
        except Exception:
            # User doesn't exist yet, skip initialization
            logger.debug(f"User {username} doesn't exist in database")
            return
        
        job_settings_str = entity.get('job_settings', '')
        job_settings_empty = False
        
        # Check if job_settings is null or empty
        if not job_settings_str or job_settings_str.strip() == '':
            job_settings_empty = True
        else:
            # Also check if it's an empty JSON object
            try:
                parsed = json.loads(job_settings_str)
                if not parsed or len(parsed) == 0:
                    job_settings_empty = True
            except (json.JSONDecodeError, TypeError):
                # If it's not valid JSON, treat as empty
                job_settings_empty = True
        
        # Initialize default job settings if empty
        if job_settings_empty:
            try:
                default_job_settings = get_default_job_settings()
                # Update entity with default settings
                update_entity = {
                    'PartitionKey': entity.get('PartitionKey', username),
                    'RowKey': entity.get('RowKey', '0'),
                    'job_settings': json.dumps(default_job_settings),
                    'job_scheduling_enabled': entity.get('job_scheduling_enabled', True)
                }
                # Preserve other existing fields
                for key, value in entity.items():
                    if key not in update_entity:
                        update_entity[key] = value
                
                # Save to database
                users_table.upsert_entity(update_entity)
                
                # Use the updated entity
                entity = update_entity
                job_settings_str = json.dumps(default_job_settings)
                
                logger.info(f"Initialized default job settings for user {username}")
            except Exception as e:
                logger.warning(f"Failed to initialize default job settings for {username}: {e}")
                # Continue with existing (empty) settings
        
        settings = {
            'job_settings': job_settings_str,
            'job_scheduling_enabled': entity.get('job_scheduling_enabled', True),
            'last_updated': entity.get('last_updated')
        }
        
        with user_settings_cache_lock:
            user_settings_cache[username] = settings
            
        logger.info(f"Refreshed user settings cache for user {username}")
        
    except Exception as e:
        logger.error(f"Failed to refresh user settings cache for user {username}: {e}")

def warm_user_settings_cache():
    """Warm up user settings cache for all users"""
    try:
        if users_table is None:
            return
            
        entities = users_table.list_entities()
        for entity in entities:
            username = entity['PartitionKey']
            refresh_user_settings_cache(username)
            
        logger.info(f"Warmed up user settings cache for all users")
        
    except Exception as e:
        logger.error(f"Failed to warm up user settings cache: {e}")

def periodic_user_settings_refresh():
    """Periodically refresh user settings cache"""
    import time
    while True:
        try:
            warm_user_settings_cache()
            time.sleep(300)  # Refresh every 5 minutes
        except Exception as e:
            logger.error(f"Error in periodic user settings refresh: {e}")
            time.sleep(60)  # Wait 1 minute before retrying

def warm_cache_for_active_users():
    """Warm up cache for active users"""
    try:
        if heroaccounts_table is None:
            return
            
        # Get all unique users from the accounts table
        entities = heroaccounts_table.list_entities()
        users = set()
        for entity in entities:
            users.add(entity['PartitionKey'])
        
        for username in users:
            refresh_user_cache(username)
            
        logger.info(f"Warmed up cache for {len(users)} active users")
        
    except Exception as e:
        logger.error(f"Failed to warm up cache for active users: {e}")

def periodic_cache_refresh():
    """Periodically refresh cache for active users"""
    import time
    while True:
        try:
            warm_cache_for_active_users()
            time.sleep(1800)  # Refresh every 30 minutes
        except Exception as e:
            logger.error(f"Error in periodic cache refresh: {e}")
            time.sleep(300)  # Wait 5 minutes before retrying
