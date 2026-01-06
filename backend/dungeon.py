from character import Character
from cache_utils import get_cached_accounts
from log import get_user_logger
from utils import wait_for_battle_completion
from bs4 import BeautifulSoup
import re, time, json

skill_settings = {
    '邪皇':     {
        'default':          ('破甲式0人', {'心眼式', '灭情战意'}),
        '凤凰':             ('定身式0人', {'心眼式', '灭情战意'}),
    },
}

dungeon_map = {'天堂瀑布': 2006,
                '冰火石窟': 2005,
                '咸阳暗道': 3014,
                '剑门长道(困难)': 2003,
                '地狱幻境': 2004,
}

def enter_dungeon(character: Character, dungeon_id: int, dungeon_type: str = '') -> bool:
    character.get_info(short=True)
    character.check_items()
    character.command('全部修理')
    if character.life < character.minimal_life:
        character.take_medicine()
    character.command.activate_beauty_card('软玉温香')

    scene_data = character.command.get_scene_data()
    if scene_data is None:
        if character.training_status == '训练中': 
            character.user_logger.info(f'{character.name}: 角色正在训练，终止训练')
            character.command('终止训练')
            character.training_status = '正常'
    elif scene_data.get('s_s2',{}).get('id') == str(dungeon_id) and scene_data.get('s_monster'):
        dungeon_name = scene_data.get('s_s2',{}).get('name')
        character.user_logger.info(f'{character.name}: 已经进入副本: {dungeon_name}')
        return True

    dungeon_scene = int(dungeon_id / 1000) * 1000
    # character.user_logger.info(f'{character.name}: 副本: {dungeon_name}@{dungeon_scene}')
    ret = character.command('进入大副本', id=dungeon_scene)
    if ret.get('error'):
        if '你当前正在武馆中' in ret.get('result'):
            character.user_logger.info(f'{character.name}: 当前在武馆中，离开武馆')
            character.command('离开武馆')
            character.command('进入大副本', id=dungeon_scene)
        else:
            character.user_logger.error(f'{character.name}: 进入大副本{dungeon_scene}失败: {ret.get('result')}')
            return False

    scene_data = character.command('副本场景', id=dungeon_id)
    if not scene_data:
        character.user_logger.error(f'{character.name}: 进入副本{dungeon_id}失败')
        return False

    dungeon_name = scene_data.get('s_s2',{}).get('name')
    if scene_data.get('s_3_arr') and not scene_data.get('s_monster'):
        entrance = scene_data.get('s_3_arr')
        if len(entrance) == 1:
            character.user_logger.info(f"{character.name}: 找到副本入口: {entrance[0].get('name')}@{dungeon_name}")
            entrance_id = entrance[0]['id']
            entrance_name = entrance[0]['name']
        else:
            entrance_name = ''
            character.user_logger.info(f"{character.name}: 找到多个副本入口: {entrance[0].get('name')}, {entrance[1].get('name')}")
            if dungeon_type:
                for entrance in entrance:
                    if dungeon_type in entrance['name']: 
                        entrance_name = entrance['name']
                        entrance_id = entrance['id']
                        break
            if not entrance_name:
                character.user_logger.error(f'{character.name}: 未找到副本入口: {dungeon_type}')
                return False
        character.user_logger.info(f"{character.name}: 进入副本: {entrance_name}@{dungeon_name}")
        ret = character.command('查看副本入口', id=entrance_id)
        script_code = ret.get('script_code', '')
        if ret.get('error') and not script_code:
            character.user_logger.error(f'{character.name}: 查看副本{entrance_name}失败: {ret.get('result')}')
            return False
        if script_code:
            # Extract first scene_id from script_code like: fnEnterThirdScene( 2132, 1, 0, 1 );
            m = re.search(r'fnEnterThirdScene\s*\(\s*(\d+)', script_code)
            scene_id = int(m.group(1)) if m else entrance_id
        else:
            scene_id = entrance_id
        scene_data = character.command('进入副本入口', id=scene_id)
        scene_data = character.command.get_scene_data()
        if scene_data.get('error'):
            time.sleep(5)
            scene_data = character.command('进入副本入口', id=scene_id)
            if scene_data.get('error'):
                character.user_logger.error(f'{character.name}: 进入副本入口{scene_id}失败: {scene_data.get('result')}')
                return False
    
    return True

def invite_group(character: Character, scene_data: dict, team: list[tuple]) -> list:
    new_team = []
    for teammate, _ in team:
        for role in scene_data.get('s_roles', []):
            if role.get('role_id') == teammate.role_id:
                character.user_logger.info(f'{character.name}: 邀请 {teammate.name} 组队')
                ret = character.command('邀请组队', id=role.get('role_id'))
                group_id = ret.get('group_id')
                if not group_id:
                    character.user_logger.error(f'{character.name}: 邀请 {teammate.name} 组队失败')
                    continue

                teammate.command('加入队伍', id=group_id)
                scene_data = character.command.get_scene_data()
                for member in scene_data.get('s_group_role'):
                    if member.get('role_id') == teammate.role_id:
                        character.user_logger.info(f'{character.name}: {teammate.name} 成功加入队伍')
                        new_team.append(teammate)
                        if len(new_team) == len(team):
                            break

    return new_team

def invite_duel_group(character: Character, scene_data: dict, team: list) -> list:
    new_team = []
    for teammate in team:
        ret = character.command('邀请组队', id=teammate.duel_role_id, is_duel_command=True)
        group_id = ret.get('group_id')
        if not group_id:
            character.user_logger.error(f'{character.name}: 邀请 {teammate.name} 跨服组队失败')
            continue

        teammate.command('加入队伍', id=group_id, is_duel_command=True)
        scene_data = character.command.get_scene_data(is_duel_command=True)
        if scene_data:
            for member in scene_data.get('s_group_role', []):
                if member.get('role_id') == teammate.duel_role_id:
                    character.user_logger.info(f'{character.name}: {teammate.name} 成功加入跨服队伍')
                    new_team.append(teammate)
                    if len(new_team) == len(team):
                        break

    return new_team

def fight_dungeon(character: Character, team: list[tuple], target_level: str = '', role_function: str = '') -> bool:
    # character.set_skills()
    new_team = []
    timeout = 300  # 5 minutes in seconds
    elapsed = 0
    interval = 5
    scene_data = character.command.get_scene_data()
    if scene_data.get('s_group_role'):
        for member in scene_data.get('s_group_role'):
            for teammate, _ in team:
                if member.get('role_id') == teammate.role_id:
                    character.user_logger.info(f'{character.name}: {teammate.name} 成功加入队伍')
                    new_team.append(teammate)
                    break
                if len(new_team) == len(team):
                    break

    while len(new_team) != len(team) and elapsed < timeout:
        character.user_logger.info(f'{character.name}: 等待组队中，当前队伍人数: {len(new_team)}')
        time.sleep(interval)
        elapsed += interval
        scene_data = character.command.get_scene_data()
        if not scene_data:
            continue
        new_team = invite_group(character, scene_data, team)

    if len(new_team) != len(team):
        character.user_logger.error(f'{character.name}: 等待组队超时（5分钟）')
        return False

    protect_member = character if role_function == '护' else None
    if not protect_member:
        for teammate, position in team:
            if position == '护':
                protect_member = teammate
                break
    if protect_member:
        protect_member.command('组队战术')
        final_form_data = [('sequence_input[]', str(character.role_id)), ('sequence_tac', '12')]
        protect_member.user_logger.debug(f'{protect_member.name}: 表单数据: {final_form_data}')
        
        result = protect_member.command.post('设置战术', data=final_form_data)
        protect_member.user_logger.info(f'{protect_member.name}: 护阵者{result.get('success')}')

    scene_data = character.command.get_scene_data()
    dungeon_name = scene_data.get('s_s2',{}).get('name')
    repeat = 3
    while True:
        scene_data = character.command.get_scene_data()
        current_scene = scene_data.get('s_s3',{}).get('name')
        character.user_logger.info(f'{character.name}: 当前在场景: {current_scene}')
        if target_level and target_level == current_scene:
            character.user_logger.info(f'{character.name}: 达到目标位置: {current_scene}，退出当前副本')
            break
        if scene_data.get('s_monster'):
            monster_id = scene_data.get('s_monster')[0].get('monster_id')
            monster_name = scene_data.get('s_monster')[0].get('type_name')
            ret = character.command('副本挑战', id=monster_id)
            count = 0
            while ret.get('error'):
                character.user_logger.info(f"{character.name}: {ret['result']}")
                time.sleep(4)
                count += 1
                if count >= 5:
                    character.user_logger.error(f'{character.name}: 挑战 {monster_name} 失败：{ret}')
                    break
                ret = character.command('副本挑战', id=monster_id)
            if ret.get('error'):
                break

            combat_id = ret.get('success', 0)
            if combat_id == 0:
                character.user_logger.error(f'{character.name}: 挑战 {monster_name} 失败：{ret}')
                break

            win = wait_for_battle_completion(character.command, character.name, combat_id, character.user_logger)
            character.user_logger.info(f'{character.name}: 挑战 {monster_name} {'成功' if win else '失败'}')
            if win:
                time.sleep(3)
            else:
                repeat -= 1
                if repeat > 0:
                    character.get_info(short=True)
                    if character.status == '死亡':
                        character.command('复活')
                    for teammate in new_team:
                        teammate.get_info(short=True)
                        if teammate.status == '死亡': teammate.command('复活')
                    character.user_logger.info(f'{character.name}: 挑战 {monster_name} 失败，重试 {repeat} 次，继续挑战')
                    continue
                else:
                    character.user_logger.error(f'{character.name}: 挑战 {monster_name} 失败：{ret}')
                    break
        else:
            character.user_logger.error(f'{character.name}: 已经通关副本 {dungeon_name}')
            break

    character.get_info(short=True)
    if character.status == '死亡':
        character.user_logger.error(f'{character.name}: 死亡，终止副本')
        character.command('复活')
    for teammate in new_team:
        character.user_logger.info(f'{character.name}: 踢 {teammate.name} 出队伍')
        character.command('踢出队伍', id=teammate.role_id)
        teammate.get_info(short=True)
        if teammate.status == '死亡': teammate.command('复活')

    return True

def character_dungeon(character: Character, dungeon_settings: list, accounts: dict, goback_training: bool = True):
    dungeon_count, dungeon_saved_progress = character.get_dungeon_progress()
    if dungeon_count == 2 and not dungeon_saved_progress:
        character.user_logger.info(f'{character.name}: 今天的副本已经打完了，明天再来吧')
        return

    dungeon_numbers = [0, 1, 2]
    target_reached = False
    if dungeon_saved_progress:
        target_reached = False
        for dungeon in dungeon_settings:
            if dungeon.get('副本') and dungeon.get('目标位置') == dungeon_saved_progress[1]:
                target_reached = True
                break
        if not target_reached:
            for i,dungeon in enumerate(dungeon_settings):
                if dungeon_saved_progress[0] in dungeon.get('副本'):
                    dungeon_numbers = [i]
                    break

    if target_reached and dungeon_count == 2:
        character.user_logger.info(f'{character.name}: 今天已经打完了所有副本，明天再来吧')
        return

    if not dungeon_settings[0].get('副本'):
        character.user_logger.error(f'{character.name}: 未设置副本')
        return

    if dungeon_count >= 1:
        character.command.activate_beauty_card('赵女娇娆')  # 激活美女图多一次副本

    team = []
    for i in dungeon_numbers:
        dungeon = dungeon_settings[i]
        dungeon_name = dungeon.get('副本')
        if not dungeon_name:
            character.user_logger.error(f'{character.name}: 未设置副本 (索引 {i})')
            continue
        if '#' in dungeon_name:
            dungeon_name, dungeon_type = dungeon_name.split('#')
        else:
            dungeon_type = ''

        if dungeon_name not in dungeon_map:
            character.user_logger.error(f'{character.name}: 未设置副本: {dungeon_name}')
            continue

        dungeon_id = dungeon_map[dungeon_name]
        if not enter_dungeon(character, dungeon_id, dungeon_type):
            break

        team = []
        teammate1 = dungeon.get('队员1')
        if teammate1:
            if ':' in teammate1:
                teammate1, position = teammate1.split(':')
            else:
                position = ''
            cookie = accounts.get(teammate1, {}).get('cookie')
            if cookie:
                teammate1 = Character(character.username, teammate1, cookie, character.user_logger)

                if enter_dungeon(teammate1, dungeon_id, dungeon_type):
                    team.append((teammate1, position))

        teammate2 = dungeon.get('队员2')
        if teammate2:
            if ':' in teammate2:
                teammate2, position = teammate2.split(':')
            else:
                position = ''
            cookie = accounts.get(teammate2, {}).get('cookie')
            if cookie:
                teammate2 = Character(character.username, teammate2, cookie, character.user_logger)
                if enter_dungeon(teammate2, dungeon_id, dungeon_type):
                    team.append((teammate2, position))

        fight_dungeon(character, team, dungeon.get('目标位置'), dungeon.get('角色功能'))

        if i == 0:
            character.command.activate_beauty_card('赵女娇娆')  # 激活美女图多一次副本
            for teammate, _ in team:
                teammate.command.activate_beauty_card('赵女娇娆')  # 激活美女图多一次副本

    if goback_training:
        character.return_home_and_train()
        for teammate, _ in team:
            teammate.return_home_and_train()

def enter_duel_dungeon(character: Character, dungeon_name: str, dungeon_id: int) -> bool:
    if not hasattr(character, 'duel_role_id') or not character.duel_role_id:
        character.get_duel_info(short=True)
    dungeon_scene = int(dungeon_id / 1000) * 1000
    ret = character.command('进入大副本', id=dungeon_scene, is_duel_command=True)
    if ret.get('error'):
        if '在副本内不能自行移动' in ret.get('result'):
            scene_data = character.command.get_scene_data(scene_type='callbackfnScene', is_duel_command=True)
            if scene_data and scene_data.get('s_s2',{}).get('name') == dungeon_name:
                character.user_logger.info(f'{character.name}: 已经在跨服副本{scene_data.get('s_s2',{}).get('name')}内，无需重新进入')
                return True
        character.user_logger.error(f'{character.name}: 进入跨服大副本{dungeon_scene}失败: {ret.get('result')}')
        return False

    scene_data = character.command('副本场景', id=dungeon_id, is_duel_command=True)
    if not scene_data:
        character.user_logger.error(f'{character.name}: 进入跨服副本{dungeon_name}失败')
        return False

    if not scene_data.get('s_3_arr'):
        scene_data = character.command.get_scene_data(is_duel_command=True)
        if not scene_data:
            character.user_logger.error(f'{character.name}: 进入跨服副本{dungeon_name}失败')
            return False

    if scene_data.get('s_3_arr') and not scene_data.get('s_monster'):
        entrance = scene_data.get('s_3_arr')
        if len(entrance) == 1:
            character.user_logger.info(f"{character.name}: 找到跨服副本入口: {entrance[0].get('name')}@{dungeon_name}")
            entrance_id = entrance[0]['id']
            entrance_name = entrance[0]['name']
        else:
            entrance_name = ''
            character.user_logger.info(f"{character.name}: 找到多个跨服副本入口: {entrance[0].get('name')}, {entrance[1].get('name')}")
            for entrance in entrance:
                if dungeon_name in entrance['name']: 
                    entrance_name = entrance['name']
                    entrance_id = entrance['id']
                    break
            if not entrance_name:
                character.user_logger.error(f'{character.name}: 未找到跨服副本入口: {dungeon_name}')
                return False
        character.user_logger.info(f"{character.name}: 进入跨服副本: {entrance_name}")
        ret = character.command('查看副本入口', id=entrance_id, is_duel_command=True)
        script_code = ret.get('script_code', '')
        if ret.get('error') and not script_code:
            character.user_logger.error(f'{character.name}: 查看跨服副本{entrance_name}失败: {ret.get('result')}')
            return False
        if script_code:
            m = re.search(r'fnEnterThirdScene\s*\(\s*(\d+)', script_code)
            scene_id = int(m.group(1)) if m else entrance_id
        else:
            scene_id = entrance_id

        scene_data = character.command('进入副本入口', id=scene_id, is_duel_command=True)
        if not scene_data or scene_data.get('error'):
            time.sleep(5)
            scene_data = character.command('进入副本入口', id=scene_id, is_duel_command=True)
            if scene_data and scene_data.get('error'):
                character.user_logger.error(f'{character.name}: 进入跨服副本入口{scene_id}失败: {scene_data.get('result')}')
                return False
    
    return True

def fight_duel_dungeon(character: Character, team: list, target_level: str = '') -> bool:
    new_team = []
    scene_data = character.command.get_scene_data(is_duel_command=True)
    if scene_data:
        new_team = scene_data.get('s_group_role')
        if new_team and len(new_team) == len(team):
            character.user_logger.info(f'{character.name}: 已经组好跨服队伍：{", ".join([member.get("role_name") for member in new_team])}')
            new_team = team

    timeout = 300  # 5 minutes in seconds
    elapsed = 0
    interval = 5
    while (not new_team or len(new_team) != len(team)) and elapsed < timeout:
        time.sleep(interval)
        elapsed += interval
        scene_data = character.command.get_scene_data(is_duel_command=True)
        if scene_data:
            new_team = invite_duel_group(character, scene_data, team)

    if len(new_team) != len(team):
        character.user_logger.error(f'{character.name}: 等待组队超时（5分钟）')
        return False

    dungeon_name = scene_data.get('s_s2',{}).get('name')
    while True:
        scene_data = character.command.get_scene_data(is_duel_command=True)
        if not scene_data:
            break
        current_scene = scene_data.get('s_s3',{}).get('name')
        character.user_logger.info(f'{character.name}: 当前在跨服场景: {current_scene}')
        if target_level and target_level == current_scene:
            character.user_logger.info(f'{character.name}: 达到目标位置: {current_scene}，退出当前跨服副本')
            break
        if scene_data.get('s_monster'):
            monster_id = scene_data.get('s_monster')[0].get('monster_id')
            monster_name = scene_data.get('s_monster')[0].get('type_name')
            ret = character.command('副本挑战', id=monster_id, is_duel_command=True)
            count = 0
            while ret.get('error'):
                character.user_logger.info(f"{character.name}: {ret['result']}")
                time.sleep(4)
                count += 1
                if count >= 5:
                    character.user_logger.error(f'{character.name}: 挑战跨服 {monster_name} 失败：{ret}')
                    break
                ret = character.command('副本挑战', id=monster_id, is_duel_command=True)
            if ret.get('error'):
                break

            combat_id = ret.get('success', 0)
            if combat_id == 0:
                character.user_logger.error(f'{character.name}: 挑战跨服 {monster_name} 失败：{ret}')
                break

            win = wait_for_battle_completion(character.command, character.name, combat_id, character.user_logger, wait_for_completion=False, is_duel_command=True)
            character.user_logger.info(f'{character.name}: 挑战跨服 {monster_name} {'成功' if win else '失败'}')
            if not win:
                break
            time.sleep(3)
        else:
            character.user_logger.error(f'{character.name}: 已经通关跨服副本 {dungeon_name}')
            break

    for teammate in new_team:
        character.user_logger.info(f'{character.name}: 踢 {teammate.name} 出队伍')
        character.command('踢出队伍', id=teammate.duel_role_id, is_duel_command=True)

    return True

def character_duel_dungeon(character: Character, duel_dungeon_settings: list, accounts: dict):
    if not duel_dungeon_settings or not duel_dungeon_settings[0].get('副本'):
        character.user_logger.error(f'{character.name}: 未设置跨服副本')
        return

    for dungeon in duel_dungeon_settings:
        dungeon_name = dungeon.get('副本')
        if dungeon_name not in dungeon_map:
            character.user_logger.error(f'{character.name}: 未设置跨服副本: {dungeon_name}')
            continue

        dungeon_id = dungeon_map[dungeon_name]
        if not enter_duel_dungeon(character, dungeon_name, dungeon_id):
            continue

        team = []
        teammate1 = dungeon.get('队员1')
        if teammate1:
            cookie = accounts.get(teammate1, {}).get('cookie')
            duel_cookies = accounts.get(teammate1, {}).get('duel_cookies')
            if cookie:
                teammate1 = Character(character.username, teammate1, cookie, character.user_logger, cached_duel_cookies=duel_cookies)
                if enter_duel_dungeon(teammate1, dungeon_name, dungeon_id):
                    team.append(teammate1)

        teammate2 = dungeon.get('队员2')
        if teammate2:
            cookie = accounts.get(teammate2, {}).get('cookie')
            duel_cookies = accounts.get(teammate2, {}).get('duel_cookies')
            if cookie:
                teammate2 = Character(character.username, teammate2, cookie, character.user_logger, cached_duel_cookies=duel_cookies)
                if enter_duel_dungeon(teammate2, dungeon_name, dungeon_id):
                    team.append(teammate2)

        fight_duel_dungeon(character, team, dungeon.get('目标位置'))
