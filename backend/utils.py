import re, time, json
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from typing import Callable

def get_china_now():
    now = datetime.now()
    china_now = now.astimezone(timezone(timedelta(hours=8)))
    return china_now

def wait_for_battle_completion(command: Callable, name: str, combat_id: str, user_logger, wait_for_completion: bool = True, is_duel_command: bool = False) -> bool:
    try:
        ret = command('战斗查看', id=combat_id, is_duel_command=is_duel_command)
        while '正在准备战斗，请稍候' in ret:
            user_logger.info(f'{name}: 正在准备战斗，请稍候')
            time.sleep(2)
            try:
                ret = command('战斗查看', id=combat_id, is_duel_command=is_duel_command)
            except Exception as e:
                if 'gzip' in str(e).lower() or 'decompress' in str(e).lower():
                    user_logger.warning(f'{name}: 战斗查看时Gzip解压错误，等待后重试: {e}')
                    time.sleep(3)
                    try:
                        ret = command('战斗查看', id=combat_id, is_duel_command=is_duel_command)
                    except Exception as retry_e:
                        user_logger.error(f'{name}: 重试后仍然失败: {retry_e}')
                        return False
                else:
                    raise

        json_objects = re.findall(r'{"t".*?}', ret)

        # If there are matches, get the last one
        if not json_objects:
            raise Exception(f'找不到战斗事件列表 {combat_id}')

        last_obj = json.loads(json_objects[-1])
        last_t_number = last_obj['t']
        match = re.search(r'combatLive.combatLiveSpeed\s*=\s*(\d+);', ret)
        speed = int(match.group(1))
        total_time = last_t_number / speed
        text = last_obj.get('w', '')
        if text:
            soup = BeautifulSoup(text, 'html.parser')
            text = soup.get_text(separator='', strip=True)

        # Wait for battle completion - don't interrupt current combat
        # The stop signal will be checked after this combat finishes
        if wait_for_completion: time.sleep(total_time)
        # 匹配"你"任意前缀(可含逗号与名字)后紧跟"技高一筹，获得了胜利"，不能让其他角色作为主语
        # 不能误判角色名技高一筹的情况，仅"你"作为主语才算胜利
        # 可包含可选空格与标点，但不能跨句子匹配（不能包含句号）
        return (
            re.search(r'你(?:[，,、\s][^。技高一筹，获得了胜利]*?)?技高一筹，获得了胜利[！!]?', text)
            is not None
        )
    except Exception as e:
        user_logger.error(f'{name}: 战斗查看时发生错误: {e}')
        return False

def extract_fan_badges(badge_soup: BeautifulSoup) -> list:

    badges = []

    # Find all tr elements
    tr_elements = badge_soup.find_all('tr')
    
    for tr in tr_elements:
        # Find img tag with titlecontent attribute
        img_tag = tr.find('img', attrs={'titlecontent': True})
        if not img_tag:
            continue
        
        # Extract name from titlecontent attribute
        # titlecontent format: "<span class='highlight'>奖励</span><br />星辰大海团队徽章*1"
        titlecontent = img_tag.get('titlecontent', '')
        
        # Parse the HTML in titlecontent to extract the badge name
        # The name appears after <br /> tag
        title_soup = BeautifulSoup(titlecontent, 'html.parser')
        # Find text after <br /> or extract all text and find the badge name pattern
        # The badge name typically contains "*" and appears after the <br /> tag
        badge_name = None
        if '<br />' in titlecontent or '<br/>' in titlecontent:
            # Split by <br /> and get the second part
            parts = re.split(r'<br\s*/?>', titlecontent, flags=re.IGNORECASE)
            if len(parts) > 1:
                # Parse the second part to get clean text
                name_part = BeautifulSoup(parts[1], 'html.parser').get_text(strip=True)
                if name_part:
                    badge_name = name_part
        else:
            # If no <br />, try to extract from the entire titlecontent
            text = title_soup.get_text(strip=True)
            # Look for pattern like "xxx*数字"
            match = re.search(r'([^*]+[*]\d+)', text)
            if match:
                badge_name = match.group(1)
        
        # Find anchor tag with onclick attribute containing the id
        anchor_tag = tr.find('a', attrs={'onclick': True})
        if not anchor_tag:
            continue
        
        # Extract id from onclick attribute
        # onclick format: 'process.start ();loader.refreshCache();loader.get ( "/modules/ore.php?act=change&id=12935");'
        onclick = anchor_tag.get('onclick', '')
        id_match = re.search(r'/modules/ore\.php\?act=change&id=(\d+)', onclick)
        
        # Extract required item (所需道具)
        # Look for <strong> tag with titlecontent attribute that contains the required item
        required_item = None
        strong_tag = tr.find('strong', attrs={'titlecontent': True})
        required_item = strong_tag.get('titlecontent', '').strip().split('x')
        required_quantity = int(required_item[1])
        required_item = required_item[0]
        
        if id_match and badge_name and required_item:
            badge_id = int(id_match.group(1))
            badge_data = {
                'name': badge_name,
                'id': badge_id,
                'required_item': required_item,
                'required_quantity': required_quantity
            }
            badges.append(badge_data)
    
    return badges

