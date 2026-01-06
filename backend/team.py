import re
from bs4 import BeautifulSoup

from character import Character
from cache_utils import get_cached_account
from log import logger

def _extract_wuguan_id_by_name(soup: BeautifulSoup, target_name: str) -> int:
    """
    Find the 武馆 id for a given 武馆名称 on the 武馆列表/查找页面.

    The list renders links like:
      <a href="javascript:void(0);" onclick="view_team ( 2551 )" title="大富翁">大富翁</a>

    This function locates the anchor by its visible text (exact match) or title,
    then parses the id from the onclick attribute.

    Args:
        soup: BeautifulSoup object for the 武馆列表/查找页面
        target_name: 武馆名称 (exact text)

    Returns:
        int: 武馆 id if found; otherwise -1
    """
    try:
        if not soup or not target_name:
            return -1

        # Find exact match anchor and parse id
        def normalize_text(value: str) -> str:
            if value is None:
                return ''
            return value.replace('\u00A0', '').replace('\xa0', '').strip()

        target_norm = normalize_text(target_name)
        anchor = None
        for a in soup.find_all('a'):
            text = normalize_text(a.get_text())
            title = normalize_text(a.get('title'))
            if text == target_norm or title == target_norm:
                anchor = a
                break

        if not anchor:
            logger.warning(f"POST search did not locate anchor for name: {target_name}")
            return -1

        onclick_value = anchor.get('onclick') or ''
        m = re.search(r'view_team\s*\(\s*(\d+)\s*\)', onclick_value)
        if not m:
            logger.warning(f"POST search found anchor but no view_team onclick for: {target_name}")
            return -1

        wuguan_id = int(m.group(1))
        logger.debug(f"POST search extracted wuguan id for '{target_name}': {wuguan_id}")
        return wuguan_id
    except Exception as e:
        logger.error(f"Error during POST search for wuguan '{target_name}': {e}")
        return -1

def _extract_farm_items(soup, page=1, fame_type='team_farm_feed'):
    farm_items = []
    # Find all <a> tags with onclick containing team_farm_feed
    feed_links = soup.find_all('a', onclick=re.compile(f'{fame_type}'))
    for link in feed_links:
        onclick_attr = link.get('onclick', '')
        # Extract first four numbers from team_farm_feed(farm_id, team_id, creature_type, bui_id, ...)
        match = re.search(rf'{fame_type}\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', onclick_attr)
        if match:
            farm_id_val = int(match.group(1))
            team_id_val = int(match.group(2))
            creature_type = int(match.group(3))
            bui_id = int(match.group(4))
            item = {
                'farm_id': farm_id_val,
                'team_id': team_id_val,
                'creature_type': creature_type,
                'bui_id': bui_id,
                'page': page,
            }

            if fame_type == 'team_farm_feed':
                # Extract item name and owner from the corresponding <td> with image
                item_name = None
                owner_name = None
                # Find the parent <td> of the feed link, then find the previous sibling <td> with the image
                feed_td = link.find_parent('td')
                if feed_td:
                    # Find the previous sibling <td> with class "highlight small_font" that contains the image
                    prev_td = feed_td.find_previous_sibling('td', class_='highlight small_font')
                    if prev_td:
                        img_tag = prev_td.find('img')
                        if img_tag and img_tag.get('titlecontent'):
                            titlecontent = img_tag.get('titlecontent')
                            # Parse titlecontent: "钟乳兽幼崽<br>主人:WBAStar<br>种植时间:2025-11-25"
                            parts = titlecontent.split('<br>')
                            if len(parts) >= 1:
                                item_name = parts[0].strip()
                            if len(parts) >= 2 and '主人:' in parts[1]:
                                owner_name = parts[1].replace('主人:', '').strip()
                
                item['item_name'] = item_name
                item['owner_name'] = owner_name

            farm_items.append(item)

    return farm_items

class Team:
    def __init__(self, character: Character):
        self.character = character
        self.user_logger = character.user_logger
        self.command = character.command
        self.username = character.username
        self.name = character.name

    def team_foster(self):
        try:
            soup = self.command('奇珍园')
            # Extract team id from onclick="dialog.close(); fnEnterTeamScene( 3100 , 1 , 0);"
            planting_count = 0
            assist_count = 0
            total_occupied = 0

            # Extract three counts from farm_title: planting count, assist count, total occupied land
            farm_title_div = soup.find('div', class_='farm_title')
            if farm_title_div:
                title_text = farm_title_div.get_text(strip=True)
                # Extract numbers before '/' in each section: "今日您已种植 0 / 10 次，协助 0 / 30 次，总占地 6 / 6"
                # Pattern: number before "/" in each section
                matches = re.findall(r'(\d+)\s*/\s*\d+', title_text)
                if len(matches) >= 3:
                    planting_count = 10 - int(matches[0])  # 今日您已种植 count
                    assist_count = 15 - int(matches[1])    # 协助 count
                    total_occupied = 6 - int(matches[2])   # 总占地 count

            # Extract farm items if assist_count < 15
            for page in range(1, 7):
                soup = self.command('奇珍园', id=page)
                if page == 1:
                    farm_items = _extract_farm_items(soup, page=page)
                else:
                    farm_items += _extract_farm_items(soup, page=page)

            for item in farm_items:
                id = f"{item['farm_id']}&team_id={item['team_id']}&creature_type={item['creature_type']}&bui_id={item['bui_id']}&page={item['page']}"
                if item['creature_type'] == 4:
                    command = '收获'
                elif assist_count > 0:
                    command = '浇水培养'
                    assist_count -= 1
                else:
                    continue

                ret = self.command(command, id=id)
                message = ''
                if isinstance(ret, dict) and ret.get('message'):
                    message_soup = BeautifulSoup(ret['message'], 'html.parser')
                    span_tag = message_soup.find('span', class_='highlight')
                    if span_tag:
                        span_text = span_tag.get_text(strip=True)
                        message = '获得了' + span_text

                self.user_logger.info(f'{self.name}: {command} - {item['owner_name']}的{item['item_name']} {message}')

            planting_count = min(planting_count, total_occupied)
            for page in range(1, 7):
                soup = self.command('奇珍园', id=page)
                farm_items = _extract_farm_items(soup, page=page, fame_type='team_farm_plant')
                for item in farm_items:
                    if planting_count <= 0:
                        break
                    id = f"{item['farm_id']}&team_id={item['team_id']}&creature_type={item['creature_type']}&bui_id={item['bui_id']}&page={item['page']}"
                    soup = self.command('种植', id=id)
                    if soup.get('error'):
                        break
                    
                    # Parse the form to extract hidden fields and first radio button value
                    form = soup.find('form')
                    if form:
                        # Extract first radio button value
                        first_radio = form.find('input', {'type': 'radio', 'name': 'radio_farm_plant_base'})
                        if not first_radio:
                            break
                        
                        form_data = {
                            'team_id': item['team_id'],
                            'farm_id': item['farm_id'],
                            'bui_id': item['bui_id'],
                            'page': item['page'],
                            'radio_farm_plant_base': first_radio.get('value', '')
                        }
                        # Extract item name from the label
                        radio_id = first_radio.get('id', '')
                        label = form.find('label', {'for': radio_id})
                        item_name = label.get_text(strip=True)
                            
                        # Submit the form
                        ret = self.command.post('种植提交', form_data)
                        planting_count -= 1
                            
                        if isinstance(ret, dict) and ret.get('result'):
                            message = ret.get('result', '')
                            self.user_logger.info(f'{self.name}: 种植 - {item_name} - {message}')
                            ret = self.command('浇水培养', id=id)
                            message = ''
                            if isinstance(ret, dict) and ret.get('message'):
                                message_soup = BeautifulSoup(ret['message'], 'html.parser')
                                span_tag = message_soup.find('span', class_='highlight')
                                if span_tag:
                                    span_text = span_tag.get_text(strip=True)
                                    message = '获得了' + span_text

                            self.user_logger.info(f'{self.name}: 浇水培养 - {self.name}的{item_name} {message}')
                        if planting_count <= 0:
                            break
                
        except Exception as e:
            self.user_logger.error(f'{self.name}: 奇珍园失败: {e}')

    def team_fight(self):
        _standpoint_map = { '0': '护馆', '1': '旁观', '2': '踢馆' }

        cached_account = get_cached_account(self.username, self.name)
        wuguan_name = cached_account.get('common_settings', {}).get('武馆', None)
        if not wuguan_name:
            self.user_logger.error(f'{self.name}: 未设置武馆')
            return

        scene_data = self.command.get_scene_data(scene_type='callbackInitTeamScene')
        if scene_data and scene_data.get('team_name') == wuguan_name and scene_data.get('ntsname') == '玄武门':
            standpoint = _standpoint_map[scene_data.get('myStandPoint')]
            self.user_logger.info(f'{self.name}: 已经在{wuguan_name} 玄武门 {standpoint} ')
            if standpoint == '踢馆':
                self.user_logger.info(f'{self.name}: 破坏{wuguan_name}武馆')
                self.command('武馆破坏')
            else:
                self.user_logger.info(f'{self.name}: 修复{wuguan_name}武馆')
                self.command('武馆修复')
            return

        soup = self.command('武馆列表')
        payload = {
            'country': '0',      # <select name="country">
            'search_var': wuguan_name,    # <input name="search_var">
        }
        payload['chk_open_team'] = '1'  # <input type="checkbox" name="chk_open_team" value="1">

        # Submit POST to the same command endpoint used for 武馆列表
        soup = self.command.post('武馆搜寻', data=payload)
        if not soup or '闭馆中' in soup.get_text():
            self.user_logger.error(f'{self.name}: 当前武馆: {wuguan_name} 闭馆中')
            return

        wuguan_id = _extract_wuguan_id_by_name(soup, wuguan_name)

        if wuguan_id == -1:
            self.user_logger.error(f'{self.name}: 未找到当前开放的武馆: {wuguan_name}')
            return

        ret = self.command('护馆', id=wuguan_id)
        if ret.get('error') and ret.get('result') != '你已经在该武馆驻地中！':
            self.user_logger.error(f'{self.name}: 护馆失败: {ret.get('error')}, 尝试踢馆')
            ret = self.command('踢馆', id=wuguan_id)
            if ret.get('error') and ret.get('result') != '你已经在该武馆驻地中！':
                self.user_logger.error(f'{self.name}: 踢馆失败: {ret.get('error')}')
                return
        self.user_logger.info(f'{self.name}: 进入玄武门')
        soup = self.command('玄武门', id=wuguan_id)

        scene_data = self.command.get_scene_data(scene_type='callbackInitTeamScene')
        if not scene_data or scene_data.get('team_name') != wuguan_name or scene_data.get('ntsname') != '玄武门':
            self.user_logger.error(f'{self.name}: 进入{wuguan_name}玄武门失败:')
            return

        standpoint = _standpoint_map[scene_data.get('myStandPoint')]
        self.user_logger.info(f'{self.name}: 进入{wuguan_name} 玄武门 {standpoint} 成功')
        if standpoint == '踢馆':
            self.command.activate_beauty_card('纤纤魏女')
            self.command.activate_beauty_card('婀娜娥皇')
        else:
            self.command.activate_beauty_card('楚女善饰')
            self.command.activate_beauty_card('俏皮妹喜')
