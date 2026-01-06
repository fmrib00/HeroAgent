import threading
import inspect
from typing import Callable, Optional

from character import Character
from cache_utils import get_cached_accounts
from log import setup_logging, get_user_logger
from dungeon import character_dungeon, character_duel_dungeon
from team import Team

# Setup logging
logger = setup_logging()

def _execute_for_accounts(
    username: str,
    account_names: Optional[list] = None,
    operation_name: str = "operation",
    operation_callback: Callable[[Character], None] = None,
    use_threading: bool = True
):
    """
    Generic helper to execute operations on accounts with optional threading.
    
    Args:
        username: The username
        account_names: List of account names to process (None means all accounts)
        operation_name: Name of the operation (used for thread naming and logging)
        operation_callback: Function that takes a Character instance and performs operations
        use_threading: If True, each account runs in a separate thread
    """
    if operation_callback is None:
        logger.warning(f"No operation callback provided for {operation_name}")
        return
    
    cached_accounts = get_cached_accounts(username)
    user_logger = get_user_logger(username)
    
    # Filter accounts based on selection
    if account_names is None or len(account_names) == 0:
        accounts_to_process = cached_accounts
    else:
        accounts_to_process = {name: cached_accounts[name] for name in account_names if name in cached_accounts}
    
    def process_account(account_name: str, account_data: dict):
        """Process a single account"""
        try:
            character = Character(username, account_name, account_data['cookie'], user_logger)
            # Check if callback accepts additional parameters (account_data, cached_accounts)
            sig = inspect.signature(operation_callback)
            param_count = len(sig.parameters)
            if param_count >= 3:
                # Callback accepts character, account_data, and cached_accounts
                operation_callback(character, account_data, cached_accounts)
            else:
                # Backward compatible: only pass character
                operation_callback(character)
        except Exception as e:
            logger.exception(f"Failed to execute {operation_name} for {account_name}@{username}: {e}")
    
    if use_threading:
        # Create and start threads for each account
        threads = []
        for account_name, account_data in accounts_to_process.items():
            thread = threading.Thread(
                target=process_account,
                args=(account_name, account_data),
                name=f"{operation_name}_{account_name}"
            )
            thread.start()
            threads.append(thread)
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
    else:
        # Sequential processing
        for account_name, account_data in accounts_to_process.items():
            process_account(account_name, account_data)

def capture_slave(username: str, account_names: list = None):
    """capture slave for a user"""
    cached_accounts = get_cached_accounts(username)
    user_logger = get_user_logger(username)
    
    # Filter accounts based on selection
    if account_names is None or len(account_names) == 0:
        # If no accounts specified, use all accounts
        slave_accounts = cached_accounts.copy()
    else:
        # Use only selected accounts
        slave_accounts = {name: cached_accounts[name] for name in account_names if name in cached_accounts}
    
    org_slave_accounts = slave_accounts.copy()
    for account_name, account_data in org_slave_accounts.items():
        if account_name not in slave_accounts:
            user_logger.info(f"跳过{account_name}，刚刚参加过奴隶战争")
            continue
        try:
            character = Character(username, account_name, account_data['cookie'], user_logger)
            _, previous_owner = character.capture_slave(cached_accounts)
            if previous_owner and previous_owner in slave_accounts:
                del slave_accounts[account_name]
                del slave_accounts[previous_owner]
            if 'identity' not in character.__dict__:
                continue
            character.capture_duel_slave()

        except Exception as e:
            logger.exception(f"Failed to capture slave for {account_name}@{username}: {e}")

def morning_routines(username: str, account_names: list = None):
    """Execute morning routines for specified accounts"""
    def operation(character: Character):
        character.set_skills()
        character.auto_sign()  # 签到
        character.auto_arena()  # 托管竞技场
        character.auto_tasks()  # 托管任务
        character.auto_huanhua()  # 抽幻化球
        character.auto_diagrams()  # 抽冲锋陷阵
        character.auto_train()     # 训练
        character.daily_gift()     # 领取每日好礼
        character.guessroom_free_gift()  # 领取免费客房有礼
        character.gold_gem()     # 抽取黄金宝石
        character.torture_slaves()  # 折磨奴隶
        character.comfort_slaves()  # 安抚奴隶

        character.command.activate_beauty_card('贡献500')  # 获得500贡献值
        character.command.activate_beauty_card('韩风美人')  # 荣誉值增加10,000
        character.command.activate_beauty_card('温情骊姬')  # 获得一个大有卦石  
        character.command.activate_beauty_card('金枝玉叶')  # 精力点加12

        character.user_logger.info(f'{character.name}: 购买60级瑕疵石*999')
        character.command('商城购买', id=8595) #60级瑕疵石*999
        
        team = Team(character)
        team.team_foster()

        character.auto_gift()      # 领取礼包

        character.duel_server_daily_tasks()  # 跨服任务

        character.sea_challange()

    _execute_for_accounts(username, account_names, "morning_routines", operation)

def night_routines(username: str, account_names: list = None):
    """Execute night routines for specified accounts"""
    def operation(character: Character):
        team = Team(character)
        team.team_foster()
        character.distribute_team_energy()     # 分配武馆经验
        character.dragon_rank()
        character.duel_trial()
    
    _execute_for_accounts(username, account_names, "night_routines", operation)

def monday_routines(username: str, account_names: list = None):
    """Execute Monday-specific routines for specified accounts"""
    def operation(character: Character):
        character.auto_horse()
        character.auto_menke()
    
    _execute_for_accounts(username, account_names, "monday_routines", operation)

def wednesday_routines(username: str, account_names: list = None):
    """Execute Monday-specific routines for specified accounts"""
    def operation(character: Character):
        character.reward_exchange()
        character.command('幻境领次数')
    
    def dungeon_operation(character: Character, account_data: dict, cached_accounts: dict):
        dungeon_settings = account_data.get('duel_dungeon_settings')
        if not dungeon_settings:
            character.user_logger.error(f'{character.name}: 未设置副本')
            return
        character_duel_dungeon(character, dungeon_settings, cached_accounts)
    
    _execute_for_accounts(username, account_names, "wednesday_routines", operation)
    _execute_for_accounts(username, account_names, "duel_dungeon", dungeon_operation)

def saturday_routines(username: str, account_names: list = None):
    """ Execute saturday routine for specified accounts """
    def operation(character: Character):
        character.confidante_explore()
        character.reward_exchange()
        character.exchange_horse_stone()
        character.command('名将助阵')

    _execute_for_accounts(username, account_names, "saturday_routines", operation)

def fengyun(username: str, account_names: list = None):
    """ Execute fengyun (风云争霸) challenges for specified accounts """
    def operation(character: Character):
        character.auto_fengyun()
        character.set_skills()
    
    _execute_for_accounts(username, account_names, "fengyun", operation)

def wuguan(username: str, account_names: list = None):
    """ Execute wuguan routine for specified accounts """
    def operation(character: Character):
        team = Team(character)
        team.team_fight()
    
    _execute_for_accounts(username, account_names, "wuguan", operation)

def dungeon_and_monster(username: str, account_names: list = None):
    """ Execute dungeon routine for specified accounts """
    
    def dungeon_operation(character: Character, account_data: dict, cached_accounts: dict):
        dungeon_settings = account_data.get('dungeon_settings')
        if not dungeon_settings:
            character.user_logger.error(f'{character.name}: 未设置副本')
            return
        character_dungeon(character, dungeon_settings, cached_accounts, goback_training=False)
    
    def monster_operation(character: Character):
        character.auto_monster(goback_training=False)  # 打怪
        character.arena_reward()  # 渑池竞技场奖励
        character.auto_get_reward()  # 领取奖励
        character.donate_items()
        character.command.activate_beauty_card('艳冶柔媚')  # 激活美女图多三次抓奴隶
        team = Team(character)
        team.team_foster()
        character.duel_trial()

    _execute_for_accounts(username, account_names, "dungeon", dungeon_operation)
    _execute_for_accounts(username, account_names, "monster", monster_operation)
