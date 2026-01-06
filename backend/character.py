# Adapted Character class for heroweb backend
import re, json, time, datetime
from contextlib import contextmanager
from bs4 import BeautifulSoup
from typing import Any
import random

from command import Command
from skill import extract_auxiliary_skill, extract_main_skill, get_skill_id, aux_skill_state_id, skill_id_to_name
from utils import wait_for_battle_completion, get_china_now, extract_fan_badges
from cache_utils import update_duel_cookies

default_skills = {
    '邪皇':     ('破甲式0人', {'心眼式', '灭情战意'}),
    '武神':     ('力破千钧0天', {'伏虎势'}),
    '英豪':     ('破风枪法0地', {'霸者横栏'}),
    '剑尊':     ('斩玄剑法0天', {'举鼎式', '破天式'}),
    '天煞':     ('分身0人', {'绝情战意', '残杀战意'}),
    '剑神':     ('无我剑气0地', {'冰心剑诀', '心静通灵'}),
}

荣誉兑换列表 = {
    '福利兑换券': 101,
    '七彩灵石': 103,
}

fan_badges_cache = None
class Character:
    def __init__(self, username, character_name, cookie, user_logger=None, cached_duel_cookies=None):
        self.username = username
        self.name = character_name
        self.cookie = cookie
        if user_logger is None:
            raise ValueError(f'{self.name}: user_logger is required')
        self.user_logger = user_logger
        split = self.cookie.split(';')
        if not split[0].startswith('svr=') or not split[1].startswith('weeCookie='):
            raise Exception(f'{self.name}: Cookie 格式不正确')
        self.url = split[0].split('=')[1]
        self.headers = {
            'User-Agent': r'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/73.0.3683.103 Safari/537.36',
            'Connection':'keep-alive',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Cookie': self.cookie
        }
        self.command = Command(self.name, self.url, self.headers, user_logger)
        
        # Load duel cookies from cache if available
        if cached_duel_cookies:
            self.command.duel_cookies = cached_duel_cookies
            self.user_logger.debug(f'{self.name}: 从缓存加载跨服 cookies')

        self.jingli_reserve = 50
        self.minimal_life = 10000

    def get_info(self, short: bool = False):
        soup = self.command('home')
        elements = soup.find_all('span', class_='highlight', attrs={'title': '查看改名记录'})
        if len(elements) == 0:
            if '本次维护时间' in soup.text:
                self.user_logger.info(f'{self.name}: 当前服务器正在维护')
                return {'status': '维护中'}

            raise Exception(f'当前页面找不到角色名: {self.name}')
        a_tag = elements[0].find('a')
        if self.name != a_tag.text.strip():
            raise Exception(f'角色名设置不符: {self.name} != {a_tag.text.strip()}')

        # Search inside <script> tags (get_text() omits script contents)
        self.role_id = None
        pattern = re.compile(r"window\.fcm_role_id\s*=\s*'(\d+)(?:_FCM)?';")
        for tag in soup.find_all('script'):
            content = tag.string or tag.get_text() or ''
            m = pattern.search(content)
            if m:
                self.role_id = m.group(1)
                break
        if self.role_id is None:
            # Fallback to full HTML string
            m = pattern.search(str(soup))
            self.role_id = m.group(1) if m else None

        elements = soup.find_all('span', class_='highlight', attrs={'name': 'text_role_level'})
        level = int(elements[0].text.strip())
        self.status = '死亡' if re.search(r'点击复活">\s*死亡', str(soup)) else '正常'

        element = soup.find('div', id='point_life')['title']
        soup_life = BeautifulSoup(element, 'html.parser')
        self.life = int(soup_life.find('span', class_='highlight').text.split('/')[0].strip())
        if self.life == 0:
            self.status = '死亡'

        self.training_status = soup.find('span', id='text_stat').get_text(strip=True)

        self.jingli = int(soup.find('span', id='text_energy').get_text(strip=True))
        
        element = soup.find('div', id='point_mana')['title']
        soup_mana = BeautifulSoup(element, 'html.parser')
        self.mana = int(soup_mana.find('span', class_='highlight').text.split('/')[0].strip())

        element = soup.find('div', id='point_life')['title']
        soup_life = BeautifulSoup(element, 'html.parser')
        self.life = int(soup_life.find('span', class_='highlight').text.split('/')[0].strip())

        if short: return

        role_info = self.command.get_role_info()
        role_attr = self.command.get_role_attr()
        role_info.update(role_attr)
        self.career = role_info['职业']

        self.auxiliary_skill = extract_auxiliary_skill(str(soup))

        # get main skill
        wbdata = self.command('技能内容')
        self.main_skill = extract_main_skill(wbdata)

        self.equip_list = self.get_items_list()
        self.life_drugs = self.get_life_drugs()

        identity_td = soup.find('td', string='身份：').find_next_sibling('td')
        self.identity = identity_td.find('a').get_text(strip=True)

        # Return a summary dict
        return {
            '角色名称': self.name,
            '角色ID': self.role_id,
            '级别': level,
            '气血': self.life,
            '精力': self.jingli,
            '状态': self.status,
            '训练状态': self.training_status,
            '主动技能': self.main_skill,
            '辅助技能': self.auxiliary_skill,
            '身份': self.identity,
            **role_info
        } 
    
    def take_medicine(self, target_life: int=10000) -> None:
        items = self.get_items_list('pack', ['name', 'item_id', 'effects', 'superpose'])
        for name, item in items.items():
            if item['effects'] == '53:5000':
                qty = min(int(target_life / 5000), int(item['superpose']))
                for _ in range(qty):
                    self.command('药物补血', id=item['item_id'])
                    self.user_logger.info(f'{self.name}: 服用药物 {name}')
                return
        self.user_logger.info(f'{self.name}: 背包里没有黑玉断续膏')

    # 上光棍empty mana
    def empty_mana(self) -> None:
        equip = self.get_items_list('equip')
        weapon = list(equip.keys())[0]
        items = self.get_items_list('pack')
        item_id = items.get('光棍', None)
        if not item_id:
            self.user_logger.info(f'{self.name}: 背包里没有光棍')
            return
        self.user_logger.info(f'{self.name}: 用光棍换下当前武器 {weapon}')
        self.command('上装备', id=item_id)

        items = self.get_items_list('pack')
        item_id = items.get(weapon, None)
        if not item_id:
            raise Exception(f'{self.name}: 背包里没有 {weapon}')
        
        self.command('上装备', id=item_id)
        self.user_logger.info(f'{self.name}: 重新装备武器 {weapon}')

    def equip_weapon(self) -> None:
        items = self.get_items_list('pack', ['item_id', 'equip_type', 'weapon_class', 'can_transfer'])
        for name, item in items.items():
            if item['equip_type'] == '1' and item['weapon_class'] != '0' and name != '光棍' and item['can_transfer'] != '1':
                self.command('上装备', id=item['item_id'])
                self.user_logger.info(f'{self.name}: 重新装备武器 {name}')
                break

    def remove_weapon(self) -> str|None:
        equip = self.get_items_list('equip', keys=['item_id', 'weapon_class'])
        for name, item in equip.items():
            if item['weapon_class'] != '0':
                self.command('脱下装备', id=item['item_id'])
                self.user_logger.info(f'{self.name}: 卸下武器 {name}')
                return name
        return None

    def has_item(self, item_name: str) -> int:
        items = self.get_items_list('pack', keys='all')
        qty = 0
        for _, item in items.items():
            if item['name'] == item_name:
                qty += int(item['superpose'])
        return qty

    # type can be equip or pack
    def get_items_list(self, type='equip', keys=None) -> dict:
        wbdata = self.command('角色信息')
        pattern = re.compile(r'itemClass\.roleItems = ({.*?});', re.DOTALL)
        match = pattern.search(wbdata)
        json_block = match.group(1)
        items = json.loads(json_block)
        if not items.get(type, None):
            return {}
        if keys == 'all': return items[type]

        if keys:
            items = {x[1]['name']:{k:x[1].get(k, None) for k in keys} for x in items[type].items()}
        else:
            items = {x[1]['name']:x[1]['item_id'] for x in items[type].items()}
        return items

    def remove_item(self, item: str) -> None:
        items = self.get_items_list()
        item_id = items.get(item, None)
        if item_id is not None:
            self.command('脱下装备', id=item_id)
        self.user_logger.info(f'{self.name}: 卸下 {item}')

    def equip_item(self, item: str) -> None:
        items = self.get_items_list('pack')
        item_id = items.get(item, None)
        if item_id is not None:
            self.command('穿上装备', id=item_id)
        self.user_logger.info(f'{self.name}: 装备 {item}')

    # keep removing equipment until the life is an odd number
    def set_odd_life(self) -> bool:
        role_attr = self.command.get_role_attr()
        self.life_limit = role_attr['气血上限']
        self.user_logger.info(f'{self.name}: 当前气血上限 {self.life_limit}')
        self.equip_removed = []
        if self.life_limit % 2 == 1:
            return True

        items = list(self.equip_list.keys())[1:]    #start from 1 to skip the first item which is the weapon
        
        while self.life_limit % 2 == 0:
            if len(items) == 0:
                return False
            item = items.pop()
            self.equip_removed.append(item)
            self.remove_item(item)
            role_attr = self.command.get_role_attr()
            self.life_limit = role_attr['气血上限']
            self.user_logger.info(f'{self.name}: 当前气血上限 {self.life_limit}')
        return True

    def equip_removed_items(self) -> None:
        if self.equip_removed is None: return
        self.user_logger.info(f'{self.name}: 还原装备')

        for item in self.equip_removed:
            self.equip_item(item)
        
        self.get_info()
        self.user_logger.info(f'{self.name}: 当前气血上限 {self.life_limit}')

    @contextmanager
    def odd_life_context(self, set_odd_life: bool=False):
        if set_odd_life:
            self.user_logger.info(f'{self.name}: 设置气血上限为奇数')
            if not self.set_odd_life():
                self.equip_removed_items()
                raise Exception(f'{self.name}: 脱下所有装备后都无法得到奇数气血上限，退出挑战')
        yield
        if set_odd_life:
            self.equip_removed_items()

    def get_life_drugs(self) -> dict:
        wbdata = self.command('角色信息')
        pattern = re.compile(r'itemClass\.roleItems = ({.*?});', re.DOTALL)
        match = pattern.search(wbdata)
        json_block = match.group(1)
        items = json.loads(json_block)
        ret = []
        for _, v in items['pack'].items(): 
            if v['item_type'] == '13' and '53' in v['itemEffects']:
                effects = v['itemEffects']['53']
                soup = BeautifulSoup(effects, 'html.parser')
                match = soup.find('span')
                effect = int(match.text.strip())
                ret.append({v['name']:{'id': v['item_id'], 'effect': effect, 'qty': v['superpose']}})

        return ret

    def equip_main_skill(self, skill: str) -> None:
        res = self.command('装备技能', id=get_skill_id(skill))
        if res is None:
            self.user_logger.info(f'{self.name}: 装备主动技能 {skill} 失败')
            return
        s = skill_id_to_name(res.get('equiped_skill', {}).get('equiped_skill_id', ''))
        if s != skill:
            raise Exception(f'Failed to equip main skill {skill}')

        self.user_logger.info(f'{self.name}: 使用主动技能 {skill}')

    def equip_auxiliary_skill(self, skills: set) -> None:
        self.user_logger.info(f'{self.name}: 使用辅助技能 {skills}')

        if 'auxiliary_skill' not in self.__dict__:
            self.get_info()

        # remove auxiliary skill that is not in preset skills
        new_aux_skill = self.auxiliary_skill.copy()
        for skill in self.auxiliary_skill:
            if skill not in skills:
                new_aux_skill.remove(skill)
                self.command('移除辅助技能', id=aux_skill_state_id(skill))

        # equip auxiliary skill that is not in current auxiliary skills
        self.auxiliary_skill = new_aux_skill
        for skill in skills:
            if skill and skill not in self.auxiliary_skill:
                self.auxiliary_skill.add(skill)
                self.command('装备辅助技能', id=get_skill_id(skill))

    def capture_slave(self, accounts: dict) -> tuple[str, str]:
        if not accounts:
            self.user_logger.info(f'{self.name}: 没有找到可俘获的奴隶')
            return "没有找到可俘获的奴隶", None

        self.user_logger.info(f'{self.name}: 开始抓奴隶')
        self.get_info()
        time.sleep(2)
        if 'identity' not in self.__dict__:
            return '系统停服，无法抓奴隶', None

        if self.identity == '奴隶': 
            return "当前角色是奴隶, 不能抓奴隶", None

        if self.identity == '奴隶主':
            slaves = self.my_slaves()
            if len(slaves) >= 5:
                return "当前角色已经有5名奴隶, 不能再抓奴隶", None

        # For other identities, try to capture slaves
        soup = self.command('奴隶对象')
        if soup is None:
            self.user_logger.info(f'{self.name}: 查看奴隶对象失败')
            return "查看奴隶对象失败", None

        if soup.text.find('您今天无法再发起俘获') != -1:
            self.user_logger.info(f'{self.name}: 您今天无法再发起俘获')
            return "您今天无法再发起俘获", None

        names = []
        # Look at all rows in the table
        for tr in soup.select("table#table_duel_slavery tr"):
            span = tr.find("span")
            if span and span.get_text(strip=True) == "奴隶主":
                for a in tr.find_all("a", onclick=lambda x: x and x.startswith("fnSlaveryFight")):
                    pattern = r"fnSlaveryFight\s*\(\s*[^,]+,\s*([^,]+),\s*['\"`]([^'\"`]+)['\"`]"
                    match = re.search(pattern, str(a))
                    if match:
                        number = match.group(1).strip()
                        name = match.group(2).strip()
                        if name in accounts:
                            names.append([number, name])

        message = "没有找到可俘获的奴隶"
        previous_owner = None
        if names:
            for name_data in names:
                number, name = name_data
                cookie = accounts[name]['cookie']
                soup = self.command('夺仆清单', id=number)
                self.user_logger.info(f'{self.name}: 发现可夺仆账号 {name}，调用夺仆清单')

                target_character = Character(self.username, name, cookie, self.user_logger)
                target_slaves = target_character.my_slaves()
                # slave[2] is status; None means not serving and can be captured
                target_slaves = [slave for slave in target_slaves if slave[2] is None]
                target_slaves = sorted(target_slaves, key=lambda x: x[3], reverse=True)
                if target_slaves:
                    target = target_slaves[0][1]
                    self.user_logger.info(f'{self.name}: 从 {name} 的奴隶清单中提取到 {len(target_slaves)} 个可俘获的奴隶, 准备抓捕最老的奴隶 {target}')
                else:
                    continue

                previous_owner = name
                weapon = target_character.remove_weapon()
                try:
                    self.command('奴隶战斗', id=f'{target_slaves[0][0]}&rid={number}')
                    time.sleep(30)
                except Exception as e:
                    message = f"抓捕奴隶 {target} 失败: {e}"
                    break
                finally:
                    if weapon: target_character.equip_item(weapon)

                ret1 = self.torture_slave(target_slaves[0][0])
                ret2 = self.comfort_slave(target_slaves[0][0])
                message = f"抓捕奴隶 {target} 成功, 折磨奴隶 {ret1}, 安抚奴隶 {ret2}"
                break

        self.user_logger.info(f'{self.name}: {message}')

        return message, previous_owner
    
    def torture_slaves(self) -> None:
        """Torture all slaves with fallback logic: try pain_type_17 first, then pain_type_13 if it fails"""
        try:
            slaves = self.my_slaves()
            if not slaves:
                self.user_logger.info(f'{self.name}: 没有奴隶可以折磨')
                return
                
            for slave_id, slave_name, status, serve_time in slaves:
                print(slave_id, slave_name, status, serve_time)
                if status: continue

                self.user_logger.info(f'{self.name}: 开始尝试折磨奴隶 {slave_name} (ID: {slave_id}, 已效力: {serve_time})')
                self.torture_slave(slave_id)
        
        except Exception as e:
            self.user_logger.error(f'{self.name}: 折磨奴隶失败: {e}')

    def comfort_slaves(self) -> None:
        """Comfort all slaves by giving them clothes"""
        try:
            slaves = self.my_slaves()
            if not slaves:
                self.user_logger.info(f'{self.name}: 没有奴隶可以安抚')
                return
                
            for slave_id, slave_name, status, serve_time in slaves:
                print(slave_id, slave_name, status, serve_time)
                if status: continue

                self.user_logger.info(f'{self.name}: 开始尝试安抚奴隶 {slave_name} (ID: {slave_id}, 已效力: {serve_time})')
                self.comfort_slave(slave_id)
        
        except Exception as e:
            self.user_logger.error(f'{self.name}: 安抚奴隶失败: {e}')

    def torture_slave(self, slave_id: str) -> str:
        """Torture a specific slave with fallback logic: try pain_type_17 first, then pain_type_13 if it fails"""
        # First, get the torture form
        try:
            self.command('折磨奴隶', id=slave_id)
        except Exception as e:
            time.sleep(5)
            self.command('折磨奴隶', id=slave_id)

        # Try pain_type_17 first (关进武馆写宣传手册)
        form_data = {
            'scene_id': '0',
            'scene_type': '0', 
            'pain_type': '17',
            'slave_id': slave_id,
            'type': '1'
        }
        
        try:
            result = self.command.post('折磨奴隶提交', form_data)
            
            if result is None:
                self.user_logger.error(f'{self.name}: 折磨奴隶提交返回空结果')
            # Check if the result contains an error about the martial arts hall being closed
            elif result.get('error', False):
                # Fallback to pain_type_13 (宣传武馆)
                form_data['pain_type'] = '13'
                # Fallback to pain_type_13 (武馆驻点修建)
                form_data['pain_type'] = '14'
                form_data['scene_id'] = '3'
                form_data['scene_type'] = '0'
                result = self.command.post('折磨奴隶提交', form_data)
                
                if result is None:
                    self.user_logger.error(f'{self.name}: 折磨奴隶提交返回空结果')
                elif result.get('error', False):
                    self.user_logger.error(f'{self.name}: 折磨奴隶失败: {result.get("result", "")}')
                else:
                    self.user_logger.info(f'{self.name}: 使用武馆驻点修建选项折磨奴隶成功')
                    return '武馆驻点修建'
            else:
                self.user_logger.info(f'{self.name}: 使用关进武馆写宣传手册选项折磨奴隶成功')
                return '小黑屋'
        except Exception as e:
            self.user_logger.error(f'{self.name}: 折磨奴隶过程中出错: {e}')
        
        return '折磨奴隶失败'

    def comfort_slave(self, slave_id: str) -> str:
        """Comfort a specific slave by giving them clothes"""
        # First, get the comfort form
        rr = self.command('安抚奴隶', id=slave_id)
        time.sleep(2)
        
        # Submit with comfort_type_6 (送奴隶衣服)
        form_data = {
            'comfort_type': '6',
            'slave_id': slave_id,
            'type': '2'
        }
        
        try:
            result = self.command.post('安抚奴隶提交', form_data)
            
            if result is None:
                self.user_logger.error(f'{self.name}: 安抚奴隶提交返回空结果')
            elif result.get('error', False):
                self.user_logger.error(f'{self.name}: 安抚奴隶失败: {result.get("result", "")}')
            else:
                self.user_logger.info(f'{self.name}: 送奴隶衣服安抚成功')
                return '送奴隶衣服'
        except Exception as e:
            self.user_logger.error(f'{self.name}: 安抚奴隶过程中出错: {e}')
        return '安抚奴隶失败'

    def my_slaves(self) -> list:
        """Get list of slaves owned by this character"""
        try:
            html_content = self.command('查看奴隶')
            
            # Parse HTML to extract slave information
            soup = BeautifulSoup(html_content, 'lxml')
            slaves = []
            seen_slave_ids = set()  # Track seen slave IDs to avoid duplicates
            
            # Find all slave rows in the table
            slave_rows = soup.find_all('tr')
            
            for row in slave_rows:
                # Look for onclick attributes that contain slave IDs
                onclick_attrs = row.find_all(attrs={'onclick': True})
                
                for attr in onclick_attrs:
                    onclick = attr.get('onclick', '')
                    
                    # Extract slave ID from view_role function calls
                    if 'view_role' in onclick:
                        # Extract ID from view_role( ID )
                        import re
                        id_match = re.search(r'view_role\s*\(\s*(\d+)\s*\)', onclick)
                        if id_match:
                            slave_id = id_match.group(1)
                            
                            # Skip if we've already seen this slave ID
                            if slave_id in seen_slave_ids:
                                continue
                                
                            seen_slave_ids.add(slave_id)
                            
                            # Find the slave name from the same row
                            name_link = row.find('a', attrs={'onclick': onclick})
                            if name_link:
                                slave_name = name_link.get('title', '').strip()
                                
                                # Extract serve time from "已效力 <span class="highlight"> 1 小时 </span>"
                                serve_time = None
                                serve_time_span = row.find('span', class_='highlight')
                                if serve_time_span:
                                    serve_time_text = serve_time_span.get_text(strip=True)
                                    if serve_time_text and '小时' in serve_time_text:
                                        # Extract only the number and convert to int
                                        # Support for "1 天 10 小时" or just "10 小时" or just "1 天"
                                        days = 0
                                        hours = 0
                                        days_match = re.search(r'(\d+)\s*天', serve_time_text)
                                        hours_match = re.search(r'(\d+)\s*小时', serve_time_text)
                                        if days_match:
                                            days = int(days_match.group(1))
                                        if hours_match:
                                            hours = int(hours_match.group(1))
                                        serve_time = days * 24 + hours
                                
                                # Check for status (like "正在宣传武馆")
                                status_div = row.find('div', class_='special')
                                status = None
                                if status_div:
                                    status_text = status_div.get_text(strip=True)
                                    if status_text:
                                        status = status_text
                                
                                slaves.append([slave_id, slave_name, status, serve_time])
                                break  # Found this slave, move to next row
            
            return slaves
            
        except Exception as e:
            self.user_logger.error(f'{self.name}: 获取奴隶列表失败: {e}')
            return []

    def donate_items(self) -> list:
        items = self.get_items_list('pack', ['item_id', 'equip_type', 'can_transfer'])
        whitelist = ['60级瑕疵石']
        ret = []

        donate_lists = []
        for name, item in items.items():
            if name in whitelist:
                donate_lists.append((name, item['item_id'], 999 if name == '60级瑕疵石' else 1))
            elif item['equip_type'] != '0' and item['can_transfer'] == '1':# donate equipments
                donate_lists.append((name, item['item_id'], 1))

        for name, item_id, qty in donate_lists:
            try:
                self.command('包裹到铸造', id=f'{item_id}&quantity={qty}')
                self.command('捐献')
                self.user_logger.info(f'{self.name}: 捐献 {name} 成功')
                ret.append(f'捐献 {name} 成功')
            except Exception as e:
                self.user_logger.error(f'{self.name}: 捐献 {name} 失败: {e}')
                ret.append(f'捐献 {name} 失败: {e}')
        return ret

    def buy_combat_count(self):
        """Buy one combat count for the character"""
        try:
            self.command('幻境买次数')
            self.user_logger.info(f'{self.name}: 购买一次挑战次数成功')
            return f'购买一次挑战次数成功'
        except Exception as e:
            self.user_logger.error(f'{self.name}: 购买挑战次数失败: {e}')
            raise Exception(f'购买挑战次数失败: {e}')

    def auto_arena(self):
        """Enter the arena and return the maximum number of arena challenges available"""
        try:
            soup = self.command('竞技场')
            
            # Look for the pattern: <td align="left" class="highlight2 important">当前最多可托管竞技场挑战次数：15</td>
            # Extract the number after the colon
            highlight2_tds = soup.find_all('td', class_='highlight2 important')
            
            for td in highlight2_tds:
                text = td.get_text(strip=True)
                # Check if this td contains the arena challenge pattern
                if '当前最多可托管竞技场挑战次数：' in text:
                    # Extract the number after the colon
                    match = re.search(r'当前最多可托管竞技场挑战次数：(\d+)', text)
                    if match:
                        max_challenges = int(match.group(1))
                        self.user_logger.info(f'{self.name}: 当前最多可托管竞技场挑战次数：{max_challenges}')
                        if max_challenges == 0:
                            return
            self.command('托管竞技场')
            self.user_logger.info(f'{self.name}: 托管竞技场')
        except Exception as e:
            self.user_logger.error(f'{self.name}: 托管竞技场失败: {e}')
        

    def auto_tasks(self):
        """Enter the task and return the number of tasks completed today"""
        try:
            soup = self.command('任务')
            # Look for the pattern: <td align="left" class="highlight2 important">当前最多可托管任务数：20</td>
            # Extract the number after the colon
            highlight2_tds = soup.find_all('td', class_='highlight2 important')
            
            for td in highlight2_tds:
                text = td.get_text(strip=True)
                # Check if this td contains the arena challenge pattern
                if '当前最多可托管任务数：' in text:
                    # Extract the number after the colon
                    match = re.search(r'当前最多可托管任务数：(\d+)', text)
                    if match:
                        max_tasks = int(match.group(1))
                        self.user_logger.info(f'{self.name}: 当前当前最多可托管任务数：{max_tasks}')
                        if max_tasks == 0:
                            return
            self.command('托管任务')
            self.user_logger.info(f'{self.name}: 托管任务')
        except Exception as e:
            self.user_logger.error(f'{self.name}: 托管任务失败: {e}')

    def auto_huanhua(self):
        try:
            soup = self.command('幻化')
            if soup.text.find('50次') != -1:
                self.command('幻化50次')
                self.user_logger.info(f'{self.name}: 幻化50次')
            else:
                self.command('幻化10次')
                self.user_logger.info(f'{self.name}: 幻化10次')
        except Exception as e:
            self.user_logger.error(f'{self.name}: 幻化失败: {e}')

    def auto_diagrams(self):
        try:
            soup = self.command('冲锋陷阵')

            count_elem = soup.find('span', id='get_times')
            max_count_elem = soup.find('span', id='max_get_times')
            
            if not count_elem or not max_count_elem:
                self.user_logger.warning(f'{self.name}: 无法找到冲锋陷阵抽取次数元素')
                return
            
            count = int(count_elem.text)
            max_count = int(max_count_elem.text)

            # Extract numbers
            self.user_logger.info(f'{self.name}: 今天冲锋陷阵抽取次数: {count}/{max_count}')
            while count < max_count:
                self.command('冲锋陷阵抽取')
                count += 10
                if count >= max_count:
                    self.user_logger.info(f'{self.name}: 今天冲锋陷阵抽取次数: {count}/{max_count}')
        except Exception as e:
            self.user_logger.error(f'{self.name}: 冲锋陷阵失败: {e}')

    def auto_get_reward(self):
        try:
            self.command('竞技领奖')
            self.user_logger.info(f'{self.name}: 竞技领奖')
            self.command('任务领奖')
            self.user_logger.info(f'{self.name}: 任务领奖')
            self.command('福利查看')
            self.command('福利')
            self.user_logger.info(f'{self.name}: 领礼券福利')
        except Exception as e:
            self.user_logger.error(f'{self.name}: 领取奖励失败: {e}')

    def auto_horse(self):
        soup = self.command('战马')

        get_free = soup.find('span', id='get_free').text
        max_get_free = soup.find('span', id='max_get_free').text

        # Extract numbers
        get_free_num = int(get_free)
        max_get_free_num = int(re.search(r'\d+', max_get_free).group())
        self.user_logger.info(f'{self.name}: 本周战马抽取次数: {get_free_num}/{max_get_free_num}')
        while get_free_num < max_get_free_num:
            self.command('战马抽取')
            time.sleep(1)
            get_free_num += 10
            if get_free_num >= max_get_free_num:
                self.user_logger.info(f'{self.name}: 本周战马抽取次数: {get_free_num}/{max_get_free_num}')

    def auto_worship(self):
        soup = self.command(link='/modules/fam_explore.php?action=enter&select_type=1&callback_func_name=ajaxCallback&callback_obj_name=callbackFamExplore')
        if not soup:
            return None
        time.sleep(1)
        self.command(link='/modules/fam_explore.php?action=view&mirror_money_type=1&select_type=1')
        self.user_logger.info(f'{self.name}: 膜拜巅峰王者')

    def skill_setting(self) -> dict:
        soup = self.command('技能设置')
        # Find all rows in the table (skip the header row)
        rows = soup.find_all('tr')[1:]  # Skip first row (header)
        
        skill_configs = {}
        
        for row in rows:
            tds = row.find_all('td')
            
            if len(tds) >= 5:
                # Extract faction name from first td
                faction_text = tds[0].text.strip()
                # Remove "对抗【" and "】：" to get clean faction name
                faction = faction_text.replace('对抗【', '').replace('】：', '')
                
                # Extract selected main skill (主动技能)
                main_skill_select = tds[1].find('select')
                main_skill_option = main_skill_select.find('option', selected=True) if main_skill_select else None
                main_skill = main_skill_option.text.strip() if main_skill_option else None
                
                # Extract selected assistant skill 1 (辅助技能1)
                assist1_select = tds[2].find('select')
                assist1_option = assist1_select.find('option', selected=True) if assist1_select else None
                assist1_skill = assist1_option.text.strip() if assist1_option else None
                
                # Extract selected assistant skill 2 (辅助技能2)
                assist2_select = tds[3].find('select')
                assist2_option = assist2_select.find('option', selected=True) if assist2_select else None
                assist2_skill = assist2_option.text.strip() if assist2_option else None
                
                skill_configs[faction] = {
                    '主动技能': main_skill.split(' ')[0].strip().replace('·', '0'),
                    '辅助技能1': assist1_skill.split(' ')[0].strip().replace('·', '0'),
                    '辅助技能2': assist2_skill.split(' ')[0].strip().replace('·', '0') if assist2_skill else None
                }
        return skill_configs

    def auto_fengyun(self):
        """ Execute fengyun (风云争霸) challenges """
        try:
            soup = self.command('风云争霸')
            div = soup.find(string=re.compile('今日已发起'))
            span = div.find_next('span', class_='highlight')
            today_total = int(span.text.split('/')[0].strip())
            if today_total >= 15:
                self.user_logger.info(f'{self.name}: 风云争霸挑战次数已满')
                return

            candidates = []
            # Find all <a> tags with "发起挑战" text
            challenge_links = soup.find_all('a', string='发起挑战')

            for link in challenge_links:
                # Extract ID from onclick attribute: fnServerDuelRoleFight( 15962 )
                onclick = link.get('onclick')
                id_match = re.search(r'fnServerDuelRoleFight\(\s*(\d+)\s*\)', onclick)
                character_id = int(id_match.group(1)) if id_match else None
                
                # Get the parent <tr> to access other columns
                tr = link.find_parent('tr')
                
                # Get all td elements in this row
                tds = tr.find_all('td')
                
                # Extract name from title attribute in first td
                name_link = tds[0].find('a')
                name = name_link.get('title') if name_link else None
                
                # Extract type/faction from second td
                faction = tds[1].text.strip()
                
                # Add to candidates list
                candidates.append({
                    'name': name,
                    'id': character_id,
                    'type': faction
                })
            skills = self.skill_setting()
            for candidate in candidates:
                self.user_logger.info(f'{self.name}: 风云争霸挑战: {candidate['name']}')
                if candidate['type'] in skills:
                    try:
                        self.equip_main_skill(skills[candidate['type']]['主动技能'])
                        self.equip_auxiliary_skill({skills[candidate['type']]['辅助技能1'], skills[candidate['type']]['辅助技能2']})
                    except Exception as e:
                        pass
                self.command('风云争霸挑战', id=candidate['id'])
                soup = self.command('风云争霸')
                div = soup.find(string=re.compile('今日已发起'))
                if div and div.find_next('span', class_='highlight').text.split('/')[0].strip() == '15':
                    self.user_logger.info(f'{self.name}: 风云争霸挑战次数已满')
                    return
                time.sleep(30)
        except Exception as e:
            self.user_logger.error(f'{self.name}: 风云争霸挑战失败: {e}')

    def auto_sign(self):
        try:
            self.command('签到查看')
            self.command('签到')
            self.user_logger.info(f'{self.name}: 签到')
        except Exception as e:
            self.user_logger.error(f'{self.name}: 签到失败: {e}')

    def auto_train(self, hour: int = 12):
        self.get_info()
        if self.training_status == '训练中':
            self.user_logger.info(f'{self.name}: 角色正在训练，终止训练')
            self.command('终止训练')
        elif self.training_status == '授艺中':
            self.user_logger.info(f'{self.name}: 角色正在授艺，终止授艺')
            self.command('终止授艺')
        self.command('训练', id=hour)
        self.user_logger.info(f'{self.name}: 训练 {hour} 小时')

    def auto_gift(self) -> str:
        try:
            soup = self.command('礼包')
            
            # Find all rows in the gift package table with class "data_grid"
            rows = soup.find_all('tr')
            
            ret = ''
            exclude_list = ['7天签到礼包', '辎重营荣誉礼包']
            for i, row in enumerate(rows):
                # Check if this row has "立即领取" (claim immediately) link
                claim_link = row.find('a', string='立即领取')
                if claim_link:
                    # Extract ID from onclick attribute: awards_view ( 11032256 )
                    onclick = claim_link.get('onclick')
                    if onclick:
                        id_match = re.search(r'awards_view\s*\(\s*(\d+)\s*\)', onclick)
                        if id_match:
                            gift_id = id_match.group(1)
                            
                            # Extract gift name from the first td in this row
                            tds = row.find_all('td')
                            if tds:
                                # Find the link in the first td that contains the gift name
                                name_link = tds[0].find('a')
                                if name_link:
                                    gift_name = name_link.text.strip()
                                    if gift_name in exclude_list:
                                        continue
                                    self.command('礼包领取', id=gift_id)
                                    self.user_logger.info(f'{self.name}: 领取礼包: {gift_name}')
                                    if i % 20 == 0:
                                        self.command('整理包裹')
                                    ret += f'{gift_name}\n'
            self.command('整理包裹')
        except Exception as e:
            self.user_logger.error(f'{self.name}: 领取礼包失败: {e}')
        return ret

    def check_items(self):
        self.command('鉴定装备')
        items = self.get_items_list('temp', ['item_id', 'equip_type', 'itemEffects'])
        for name, item in items.items():
            if item.get('equip_type') == '0':
                self.command('装备入包', id=item['item_id'])
            elif item.get('itemEffects') and len(item['itemEffects']) > 2:
                self.command('装备入包', id=item['item_id'])
                self.user_logger.info(f'{self.name}: 装备入包: {name}')
        self.command('出售临时包裹')

    def free_training_if_available(self, monster_id: str):
        soup = self.command('签到查看')
        
        self.free_train_count = False
        # Extract "免费立即完成修炼" rewards from the sign-in table
        record_table = soup.find('table', id='record_list')
        if record_table:
            rows = record_table.find('tr')
            tds = rows.find_all('td')
            if len(tds) >= 4:
                reward_text = tds[1].get_text(strip=True)
                status = tds[3].get_text(strip=True)
                # Check if this row contains "免费立即完成修炼"
                if '免费立即完成修炼' in reward_text and (status == "未使用" or status == "使用中"):
                    self.free_train_count = True

        if self.training_status == '修炼中':
            response = self.command('查看修炼')
            html_content = str(response)
            
            # Extract remaining time in seconds from autoCombatTimmer.init
            delay_match = re.search(r'autoCombatTimmer\.init\s*\(\s*[\'"]auto_combat_delay[\'"]\s*,\s*(\d+)', html_content)
            delay_seconds = int(delay_match.group(1)) if delay_match else None
            
            if delay_seconds and delay_seconds > 120 and '免费立即完成修炼' in html_content:
                self.user_logger.info(f'{self.name}: 正在修炼，立即使用免费立即完成修炼')
                self.command('修炼立即完成')
                self.get_info()
                self.check_items()
                return True
            else:
                self.user_logger.info(f'{self.name}: 正在修炼，等待结束 {delay_seconds} 秒 ({delay_seconds // 60} 分钟)')
                time.sleep(delay_seconds)
                self.get_info()
                return False

        if self.free_train_count:
            self.command('修炼', id=monster_id)
            form_data = {
                'mid': monster_id,
                'select_frequency': '24',
            }
            response = self.command.post('修炼提交', form_data)
            data = json.loads(str(response)) if isinstance(response, str) else response
            
            # Strip spaces from keys to handle malformed keys like 'wealInfo '
            data = {k.strip(): v for k, v in data.items()} if isinstance(data, dict) else data
            
            # Extract benefit info from wealInfo
            weal_info = data.get('wealInfo', {})
            if weal_info and weal_info.get('weal_note') == '免费完成修炼':
                self.user_logger.info(f'{self.name}: 使用免费立即完成修炼24次')
                self.command('修炼立即完成')
                self.get_info()
                self.check_items()
                return True

        return False
    
    def fight_monster(self, monster_name: str, monster_id: str) -> bool:
        if self.status == '死亡': self.command('复活')
        if self.life < self.minimal_life:
            self.take_medicine()

        for i in range(3):
            if not self.free_training_if_available(monster_id) or self.jingli <= self.jingli_reserve:
                break

        repeat = 3
        total_count = 0
        if self.jingli > self.jingli_reserve:
            fight_count = self.jingli - self.jingli_reserve
            for i in range(fight_count):
                self.user_logger.info(f'{self.name}: 挑战 {monster_name} 第 {i + 1}/{fight_count} 次')
                ret = self.command('打怪', id=monster_id)
                if ret is None or 'error' in ret:
                    while repeat > 0: 
                        self.user_logger.info(f'{self.name}: {ret.get('result', '') if ret else '重试'}， 重试次数: {3-repeat+1}')
                        time.sleep(1)
                        ret = self.command('打怪', id=monster_id)
                        if ret and 'success' in ret: break
                        repeat -= 1
                    if repeat == 0: 
                        self.user_logger.info(f'{self.name}: 挑战 {monster_name} 失败')
                        return False
                
                total_count += 1
                repeat = 3
                if 'result' in ret and '你已经死亡' in ret['result']:
                    self.command('复活')
                    self.user_logger.info(f'{self.name}: 挑战 {monster_name} 失败，角色死亡，返回')
                    return False

                combat_id = ret.get('success', 0)
                if combat_id == 0:
                    self.user_logger.info(f'{self.name}: 找不到{monster_name}的战斗ID')
                    return False

                ret = wait_for_battle_completion(self.command, self.name, combat_id, self.user_logger)
                if not ret: return False

                if i % 20 == 19:
                    self.get_info()
                    self.check_items()
                    self.command('全部修理')
                    if self.life < self.minimal_life: self.take_medicine()
                    if self.jingli <= self.jingli_reserve: break
                    if self.training_status != '正常': 
                        self.user_logger.info(f'{self.name}: 角色正在训练，退出')
                        break

        self.user_logger.info(f'{self.name}: 挑战 {monster_name} 总次数: {total_count}')
        return True

    def auto_monster(self, goback_training: bool = True):

        self.get_info()
        if self.jingli <= self.jingli_reserve:
            self.user_logger.info(f'{self.name}: 精力{self.jingli}不足保留值{self.jingli_reserve}，跳过打怪')
            return

        if self.training_status == '训练中': 
            self.user_logger.info(f'{self.name}: 角色正在训练，终止训练')
            self.command('终止训练')
            self.training_status = '正常'
        elif self.training_status == '授艺中':
            self.user_logger.info(f'{self.name}: 角色正在授艺，终止授艺')
            self.command('终止授艺')
            self.training_status = '正常'

        # self.set_skills()
        soup = self.command('怪物导航')
        if soup is None:
            self.user_logger.warning(f'{self.name}: 无法获取怪物导航页面')
            return
        rows = soup.find_all('tr')
        location = None
        monster_name = None
        scene_id = None
        for row in rows:
            # Look for the td that contains fnMoveToScene
            move_link = row.find('a', onclick=lambda x: x and 'fnMoveToScene' in x)
            if not move_link: continue

            # Extract monster name from the span with class "text_monster"
            # Extract location from span with class "text_scene"
            monster_span = row.find('span', class_='text_monster')
            monster_name = monster_span.text.strip() if monster_span else None
            location_span = row.find('span', class_='text_scene')
            location = location_span.text.strip() if location_span else None

            onclick = move_link.get('onclick')
            # Extract the first number from fnMoveToScene( 483, 500, '铜币' )
            match = re.search(r'fnMoveToScene\s*\(\s*(\d+)', onclick)
            if not match:
                self.user_logger.warning(f'{self.name}: 无法找到怪物 {monster_name} 的场景ID')
                continue

            scene_id = match.group(1)
            if location and monster_name and scene_id:
                self.user_logger.info(f'{self.name}: 找到在 {location}, 场景ID: {scene_id} 的怪物 {monster_name} 作为修炼目标')
                break
        
        if not location or not monster_name or not scene_id:
            self.user_logger.warning(f'{self.name}: 无法找在怪物导航中找到修炼目标')
            return

        if self.training_status == '虚弱':
            self.return_home_and_recharge()
            self.training_status = '正常'

        if self.training_status == '正常':
            try:
                self.command('移动场景', id=scene_id)
            except Exception as e:
                if '你正在武馆驻地之中' in str(e):
                    self.command('离开武馆')
                    self.user_logger.info(f'{self.name}: 离开武馆')
                    self.command('移动场景', id=scene_id)
                else:
                    self.user_logger.error(f'{self.name}: 移动场景失败: {e}')
                    return

        scene_data = self.command.get_scene_data()
        if not scene_data:
            self.user_logger.warning(f'{self.name}: 无法获取场景数据')
            return

        # Find challengeable monsters in s_monster
        s_monster = scene_data.get('s_monster', {})
        found = False
        if isinstance(s_monster, dict):
            s_monster = s_monster.values()
        for monster in s_monster:
            rank_des = monster.get('rank_des', '')
            type_name = monster.get('type_name', '')
            
            # Check if this is a challengeable monster (有挑战的) and matches our target
            if '有挑战的' in rank_des and type_name == monster_name:
                monster_id = monster.get('monster_id')
                self.user_logger.info(f'{self.name}: 找到挑战怪物 {type_name}, ID: {monster_id}')
                self.command.activate_beauty_card('软玉温香')
                self.fight_monster(type_name, monster_id)
                found = True
                break
        if not found:
            self.user_logger.warning(f'{self.name}: 无法从场景 {location} 找到怪物 {monster_name}')

        if goback_training:
            self.return_home_and_train()
        self.check_items()

    def enter_duel_server(self):
        """
        Enter the cross-server duel arena (跨服竞技场).
        This establishes a session with duel.50hero.com and stores the cookies.
        Must be called before making any duel server requests.
        """
        result = self.command.enter_duel_server()
        
        # Save duel cookies to cache for persistence across requests
        if self.command.duel_cookies:
            update_duel_cookies(self.username, self.name, self.command.duel_cookies)
        
        return result

    def call_duel_api(self, api_path: str):
        """
        Make a request to the duel server API.
        Automatically enters the duel server if not already done.
        
        Args:
            api_path: The API path on duel.50hero.com, e.g., '/modules/trial.php?act=hall&action=fight&mid=46'
        
        Returns:
            Response from the duel server
        """
        # Enter duel server if we haven't yet
        if self.command.duel_cookies is None:
            self.user_logger.info(f'{self.name}: 首次访问跨服，正在进入...')
            self.enter_duel_server()
        else:
            self.user_logger.debug(f'{self.name}: 使用已缓存的跨服会话')
        
        # Make the request to duel server
        full_url = f'http://duel.50hero.com{api_path}'
        return self.command(command=None, link=full_url)

    def auto_menke(self):
        self.user_logger.info(f'{self.name}: 门客招募')
        self.command('门客招募')
        for i in range(5):
            self.command('门客招募2')

        soup = self.command('门客生成')
        div = soup.find('div', class_='wise_action_1')
        onclick_value = div['onclick']
        number = onclick_value.split('(')[1].split(')')[0]
        self.user_logger.info(f'{self.name}: 挑战简单门客: {number}')
        self.command('门客挑战', id=number)
        time.sleep(20)

        div = soup.find('div', class_='wise_action_2')
        onclick_value = div['onclick']
        number = onclick_value.split('(')[1].split(')')[0]
        self.user_logger.info(f'{self.name}: 挑战普通门客: {number}')
        self.command('门客挑战', id=number)

    def set_skills(self):
        try:
            self.get_info()
            if self.status == '死亡': self.command('复活')
            if self.mana < 1000:
                self.command('客房补血')
            self.user_logger.info(f'{self.name}: 设置默认技能 {default_skills[self.career][0]} 和 {default_skills[self.career][1]}')
            self.equip_main_skill(default_skills[self.career][0])
            self.equip_auxiliary_skill(default_skills[self.career][1])
        except Exception as e:
            self.user_logger.info(f'{self.name}: 设置默认技能失败: {e}')

    def get_duel_info(self, short: bool = False):
        # Get the initial duel server page
        initial_soup = self.command('home', is_duel_command=True)
        
        # Extract role_id from onclick="view_role ( 30464 );"
        role_id = None
        for element in initial_soup.find_all(attrs={'onclick': True}):
            onclick = element.get('onclick', '')
            if 'view_role' in onclick:
                match = re.search(r'view_role\s*\(\s*(\d+)\s*\)', onclick)
                if match:
                    role_id = match.group(1)
                    break
        
        if not role_id:
            self.user_logger.error(f'{self.name}: 无法从跨服页面提取 role_id')
            return {"error": "无法提取 role_id"}
        
        self.user_logger.info(f'{self.name}: 提取到跨服 role_id: {role_id}')
        self.duel_role_id = role_id
        # Extract character stats from the role info page
        duel_info = { "role_id": self.duel_role_id }
        if short: 
            return duel_info
        
        # Call '角色信息' command with the role_id to get detailed stats
        soup = self.command('角色信息', id=role_id, is_duel_command=True)
        
        try:
            # Extract 气血 (Health)
            life_div = initial_soup.find('div', id='point_life')
            if life_div and life_div.get('title'):
                life_match = re.search(r'(\d+)\s*/\s*(\d+)', life_div['title'])
                if life_match:
                    duel_info['气血'] = f"{life_match.group(1)} / {life_match.group(2)}"
            
            # Extract 内息 (Mana)
            mana_div = initial_soup.find('div', id='point_mana')
            if mana_div and mana_div.get('title'):
                mana_match = re.search(r'(\d+)\s*/\s*(\d+)', mana_div['title'])
                if mana_match:
                    duel_info['内息'] = f"{mana_match.group(1)} / {mana_match.group(2)}"
            
            # Extract 臂力 (Strength)
            str_div = initial_soup.find('div', id='point_str')
            if str_div and str_div.get('title'):
                str_match = re.search(r'当前臂力：<span class=highlight>(\d+)</span>\s*<span class=[\'"]?special[\'"]?>([+\d]+)</span>', str_div['title'])
                if str_match:
                    base = int(str_match.group(1))
                    bonus = int(str_match.group(2))
                    duel_info['臂力'] = f"{base} + {bonus} = {base + bonus}"
            
            # Extract 身法 (Dexterity)
            dex_div = initial_soup.find('div', id='point_dex')
            if dex_div and dex_div.get('title'):
                dex_match = re.search(r'当前身法：<span class=highlight>(\d+)</span>\s*<span class=[\'"]?special[\'"]?>([+\d]+)</span>', dex_div['title'])
                if dex_match:
                    base = int(dex_match.group(1))
                    bonus = int(dex_match.group(2))
                    duel_info['身法'] = f"{base} + {bonus} = {base + bonus}"
            
            # Extract 根骨 (Vitality)
            vit_div = initial_soup.find('div', id='point_vit')
            if vit_div and vit_div.get('title'):
                vit_match = re.search(r'当前根骨：<span class=highlight>(\d+)</span>\s*<span class=[\'"]?special[\'"]?>([+\d]+)</span>', vit_div['title'])
                if vit_match:
                    base = int(vit_match.group(1))
                    bonus = int(vit_match.group(2))
                    duel_info['根骨'] = f"{base} + {bonus} = {base + bonus}"
            
            # Extract 命中率, 躲闪率, 暴击率, 破击率 from divs with specific classes
            # 命中率 (Hit Rate)
            hit_div = soup.find('div', class_='attr_hr_lite')
            if hit_div:
                hit_span = hit_div.find('span', class_='highlight small_font')
                if hit_span:
                    duel_info['命中'] = hit_span.get_text(strip=True)
            
            # 躲闪率 (Dodge Rate)
            dodge_div = soup.find('div', class_='attr_dr_lite')
            if dodge_div:
                dodge_span = dodge_div.find('span', class_='highlight small_font')
                if dodge_span:
                    duel_info['躲闪'] = dodge_span.get_text(strip=True)
            
            # 暴击率 (Critical Rate)
            crit_div = soup.find('div', class_='attr_ds_lite')
            if crit_div:
                crit_span = crit_div.find('span', class_='highlight small_font')
                if crit_span:
                    duel_info['暴击'] = crit_span.get_text(strip=True)
            
            # 破击率 (Pierce Rate)
            pierce_div = soup.find('div', class_='attr_id_lite')
            if pierce_div:
                pierce_span = pierce_div.find('span', class_='highlight small_font')
                if pierce_span:
                    duel_info['破击'] = pierce_span.get_text(strip=True)
            
            # Extract 攻击 (Attack)
            # Find all td elements and search for the one containing '攻击：'
            for td in initial_soup.find_all('td'):
                if td.get_text(strip=True) == '攻击：':
                    attack_value = td.find_next_sibling('td')
                    if attack_value:
                        attack_match = re.search(r'(\d+)\s*-\s*(\d+)', attack_value.get_text())
                        if attack_match:
                            duel_info['攻击'] = f"{attack_match.group(1)} - {attack_match.group(2)}"
                    break
            
            # Extract 防御 (Defense)
            defense_span = initial_soup.find('span', id='text_defence')
            if defense_span:
                defense_match = re.search(r'>(\d+)<', str(defense_span))
                if defense_match:
                    duel_info['防御'] = defense_match.group(1)
            
            soup = self.command('技能信息', is_duel_command=True)
            page_html = str(soup)

            pattern = r'"equiped_skill_id"\s*:\s*"(\d+)"'
            match = re.search(pattern, page_html)
            if match:
                skill_id = match.group(1)
                skills_obj = re.search(r'window\.skills\s*=\s*(\{.*?\})\s*[;\n]', page_html, re.DOTALL)
                if skills_obj:
                    try:
                        skills = json.loads(skills_obj.group(1))
                        
                        # Search through all skill entries to find matching id
                        for key, skill_data in skills.items():
                            if skill_data.get('id') == skill_id:
                                duel_info['技能'] = skill_data['name']
                                break
                    except:
                        pass
            return duel_info
        except Exception as e:
            self.user_logger.error(f'{self.name}: 解析跨服信息失败: {e}')
            return {"error": str(e)}

    def exchange_horse_stone(self):
        self.user_logger.info(f'{self.name}: 兑换坐骑宝石')
        self.command('兑换奖励', id=2621)
        self.command('兑换奖励', id=2621)
        self.command('兑换奖励', id=2621)
        self.auto_gift()
        stone_ids = ['12213', '12214', '12215', '12216', '12217', '12218', '12219', '12220', '12221', '12222']
        for stone_id in stone_ids:
            self.command('兑换奖励', id=stone_id)
        self.auto_gift()

    def reward_exchange(self):
        reward_table = {'星辰': [2223, 2224, 2225, 2226, 2227], 
                        '福利': [845],
                        '活动': [2721, 2722, 2723, 2724, 2725, 2726, 2727, 2728, 2729, 2730, 2731, 2732, 
                                2733, 2734, 2735, 2736, 2737, 2738, 2739, 2740, 2774, 2775, 2776, 2777],
                        '珍宝换银牌': ([1206], 10),
                        '神秘奖品兑换': ([2450], 5),
                        '活跃度': [2785, 2786, 2787, 2788, 2789, 2790],
                        '庆典': [2791, 2792, 2793, 2794],
                        '蓝星换紫星': ([5000], 10),
                        '紫星换红星': ([5001], 10),
                        '联赛徽章': ([12195], 1),
                        '副本换红色星云': ([58], 10),
        }

        for name, reward in reward_table.items():
            if isinstance(reward, list):
                for item in reward:
                    self.user_logger.info(f'{self.name}: 兑换奖励: {name} - {item}')
                    self.command('兑换奖励', id=item)
            elif isinstance(reward, tuple):
                for item in reward[0]:
                    self.user_logger.info(f'{self.name}: 兑换奖励: {name} - {item}')
                    for i in range(reward[1]):
                        self.command('兑换奖励', id=item)

        self.user_logger.info(f'{self.name}: 领辎重')
        self.command('领辎重')
        self.user_logger.info(f'{self.name}: 4次贡献换铜币')
        for i in range(4): 
            time.sleep(5)
            self.command('贡献换铜币')

        self.user_logger.info(f'{self.name}: 领取地区冠军奖励')
        self.command('地区冠军')
        self.user_logger.info(f'{self.name}: 领取本服冠军奖励')
        self.command('本服冠军')

        self.auto_worship()
        self.get_benefit_reward()
        self.auto_gift()
        self.user_logger.info(f'{self.name}: 银牌兑换金牌')
        self.command('兑换奖励', id=2581)

    def get_benefit_reward(self):
        count = self.has_item('福利兑换券')
        missing_count = 4 - count
        if missing_count > 0:
            self.user_logger.info(f'{self.name}: 购买 {missing_count} 个福利兑换券')
            self.command('荣誉兑换', id=f'{荣誉兑换列表['福利兑换券']}&itemNum={missing_count}')
            count = self.has_item('福利兑换券')
        if count < 4:
            self.user_logger.info(f'{self.name}: 买福利兑换券失败, 剩余福利兑换券数量: {count}')
            return

        for item in [814, 815, 816, 817]:
            self.user_logger.info(f'{self.name}: 兑换福利奖励: {item}')
            self.command('兑换奖励', id=item)

    def capture_duel_slave(self):
        self.user_logger.info(f'{self.name}: 跨服奴隶')
        soup = self.command('跨服奴隶', is_duel_command=True)

        # Check slavery status and escape if time has passed
        slavery_div = soup.find('div', id='div_slavery')
        if slavery_div:
            # Find all highlight spans in the slavery div
            highlight_spans = slavery_div.find_all('span', class_='highlight')
            
            # First highlight span should be the identity
            if len(highlight_spans) >= 2:
                identity_span = highlight_spans[0]
                escape_time_span = highlight_spans[1]  # Second highlight span is escape time
                
                slavery_identity = identity_span.get_text(strip=True)
                if slavery_identity == '奴隶':
                    escape_time_str = escape_time_span.get_text(strip=True)
                    # Parse time: "11-02 23:20:04" (format: MM-DD HH:MM:SS)
                    try:
                        # Get current year and construct full datetime
                        current_time = get_china_now()
                        current_year = current_time.year
                        escape_time_str_full = f"{current_year}-{escape_time_str}"
                        escape_time = datetime.datetime.strptime(escape_time_str_full, "%Y-%m-%d %H:%M:%S")
                        # Make escape_time timezone-aware to match current_time (China timezone UTC+8)
                        escape_time = escape_time.replace(tzinfo=current_time.tzinfo)
                        
                        # Compare with current time
                        if escape_time < current_time:
                            self.user_logger.info(f'{self.name}: 可逃脱时间已过 ({escape_time_str}), 执行逃跑')
                            self.command('逃跑', is_duel_command=True)
                        else:
                            self.user_logger.info(f'{self.name}: 还是奴隶, 可逃脱时间: {escape_time_str}, 还需等待')
                            return
                    except Exception as e:
                        self.user_logger.warning(f'{self.name}: 解析可逃脱时间失败: {escape_time_str}, 错误: {e}')
        
        
        # Initialize variables
        fight_count = 0
        fight_max = 0
        slave_current = 0
        slave_max = 0
        current_prestige = 0
        max_prestige = 0
        
        for body_div in soup.find_all('div', class_='body'):
            for td in body_div.find_all('td'):
                # 1. Extract "已发起 0/3 场" - get current and max battle count
                if '已发起' in td.get_text():
                    highlight_span = td.find('span', class_='highlight')
                    if highlight_span:
                        match = re.search(r'(\d+)/(\d+)', highlight_span.text)
                        if match:
                            fight_count = int(match.group(1))
                            fight_max = int(match.group(2))
            
                # 2. Extract "奴隶数 0/1 个" - get current and max slave count
                if '奴隶数' in td.get_text():
                    highlight_span = td.find('span', class_='highlight')
                    if highlight_span:
                        match = re.search(r'(\d+)/(\d+)', highlight_span.text)
                        if match:
                            slave_current = int(match.group(1))
                            slave_max = int(match.group(2))
            
                # 3. Extract "威望值: 1616/8000" - get current and max prestige value
                if '威望值' in td.get_text():
                    # Find the span with id containing "self_pve_inte_num"
                    prestige_span = td.find('span', id=re.compile('self_pve_inte_num'))
                    if prestige_span:
                        current_prestige = int(prestige_span.text.strip())
                        # Find the max value after the slash
                        parent_highlight = prestige_span.find_parent('span', class_='highlight')
                        if parent_highlight:
                            match = re.search(r'/(\d+)', parent_highlight.text)
                            if match:
                                max_prestige = int(match.group(1))

        if fight_count >= fight_max:
            return

        for body_div in soup.find_all('div', class_='body'):
            # 4 Extract existing slaves
            data_table = body_div.find('table', class_='data_grid')
            if data_table:
                for tr in data_table.find_all('tr'):
                    # Find the view_role link to get slave ID and name
                    view_role_link = tr.find('a', onclick=re.compile(r'view_role'))
                    if view_role_link:
                        # Extract slave ID from onclick="view_role ( 29155 )"
                        onclick = view_role_link.get('onclick', '')
                        id_match = re.search(r'view_role\s*\(\s*(\d+)\s*\)', onclick)
                        if id_match:
                            slave_id = id_match.group(1)
                            # Get slave name from title attribute or link text
                            slave_name = view_role_link.get('title', '') or view_role_link.get_text(strip=True)
                            
                            # Extract serve time from the second td (index 1)
                            tds = tr.find_all('td')
                            serve_time = None
                            if len(tds) >= 2:
                                # Second td contains the timestamp: "11-03 15:48:58"
                                serve_time = tds[1].get_text(strip=True)
                                if serve_time < get_china_now().strftime("%m-%d %H:%M:%S"):
                                    self.command('折磨奴隶', id=slave_id, is_duel_command=True)
                                    payload = {
                                        'slave_id': slave_id,
                                        'type': '1',
                                        'scene_id': '0',
                                        'scene_type': '0',
                                        'pain_type': '3',  # 折磨（5威望值）免费
                                    }
                                    self.command.post('折磨奴隶提交', data=payload, is_duel_command=True)
                                    self.user_logger.info(f'{self.name}: 折磨奴隶 {slave_name} 成功')
                                    self.user_logger.info(f'{self.name}: 释放奴隶 - ID: {slave_id}, 名称: {slave_name}')
                                    self.command('释放奴隶', id=slave_id, is_duel_command=True)
                                    slave_current -= 1
                                    break
            

        self.user_logger.info(f'{self.name}: 奴隶数: {slave_current}/{slave_max}, 威望值: {current_prestige}/{max_prestige}, 已发起战斗: {fight_count}/{fight_max}')
        if current_prestige > 7000:
            self.user_logger.info(f'{self.name}: 威望值: {current_prestige} > 7000, 威望换联盟勋章')
            self.command('威望换勋章', is_duel_command=True)

        if slave_current >= slave_max:
            return

        # Extract slave candidates that are NOT "奴隶主" (slave owner)
        slave_candidates = []
        for tr in soup.find_all('tr'):
            # Find the status span in this row (could be purple, special, or highlight class)
            status_span = (tr.find('span', class_='special') or 
                          tr.find('span', class_='highlight'))
            if status_span:
                status_text = status_span.get_text(strip=True)
                # Skip if status is "奴隶主" (slave owner)
                if status_text == '奴隶主':
                    continue
                
                # Find the fnSlaveryFight onclick link
                fight_link = tr.find('a', onclick=re.compile(r'fnSlaveryFight'))
                if fight_link:
                    onclick = fight_link.get('onclick', '')
                    # Extract ID and name from: fnSlaveryFight( X, ID, 'NAME', Y, 1 )
                    match = re.search(r'fnSlaveryFight\s*\(\s*\d+\s*,\s*(\d+)\s*,\s*[\'"]([^\'"]+)[\'"]\s*,\s*\d+\s*,\s*1\s*\)', onclick)
                    if match:
                        candidate_id = match.group(1)
                        candidate_name = match.group(2)
                        slave_candidates.append({
                            'id': candidate_id,
                            'name': candidate_name,
                            'status': status_text
                        })

        # randomly choose a candidate
        if not slave_candidates:
            self.user_logger.info(f'{self.name}: 没有可俘获的奴隶目标')
            return
        
        random.seed(get_china_now().timestamp())
        random_candidate = random.choice(slave_candidates)
        self.user_logger.info(f'{self.name}: 随机抓捕目标 - {random_candidate["name"]}, {random_candidate["id"]}, 状态: {random_candidate["status"]}')
        ret = self.command('奴隶战斗', id=random_candidate['id'], is_duel_command=True)
        if ret.get('error'):
            self.user_logger.error(f'{self.name}: 奴隶战斗失败: {ret.get("result")}')
            return

        self.command('折磨奴隶', id=random_candidate['id'], is_duel_command=True)
        payload = {
            'slave_id': random_candidate['id'],
            'type': '1',
            'scene_id': '0',
            'scene_type': '0',
            'pain_type': '3',  # 折磨（5威望值）免费
        }
        self.command.post('折磨奴隶提交', data=payload, is_duel_command=True)
        self.user_logger.info(f'{self.name}: 折磨奴隶 {random_candidate["name"]} 成功')

    def duel_server_daily_tasks(self):
        try:
            self.user_logger.info(f'{self.name}: 跨服领军功')
            self.command('领军功', is_duel_command=True)

            for i in range(5):
                self.user_logger.info(f'{self.name}: 跨服武将探索 - 第{i+1}次')
                self.command('武将探索', is_duel_command=True)
                if i != 4: time.sleep(60)

            for i in range(6):
                ret = self.command('活跃度', is_duel_command=True, id=i+1)
                if not ret.get('error'):
                    self.user_logger.info(f'{self.name}: 跨服活跃度 - {ret.get('message')}')
                    time.sleep(2)
        except Exception as e:
            self.user_logger.error(f'{self.name}: 跨服领军功失败: {e}')

    def arena_reward(self, goback_training: bool = True):
        soup = self.command('刷新场景')
        if '离开武馆' in soup.get_text():
            self.command('离开武馆')

        soup = self.command('刷新场景')
        was_training = False
        if soup.find('div', class_='city_scene_name') is not None:
            city_scene_name = soup.find('div', class_='city_scene_name').text.strip()
            if '渑池' != city_scene_name:
                self.get_info(short=True)
                if self.training_status == '训练中':
                    self.command('终止训练')
                    was_training = True
                elif self.training_status == '授艺中':
                    self.command('终止授艺')
                    was_training = True
                self.command('前往渑池')
        else:
            self.command('前往渑池')

        soup = self.command('刷新场景')
        if soup is None:
            self.user_logger.error(f'{self.name}: 刷新场景失败，无法获取场景信息')
            return False
        city_scene_div = soup.find('div', class_='city_scene_name')
        if city_scene_div is None:
            self.user_logger.error(f'{self.name}: 无法找到场景名称元素')
            return False
        city_scene_name = city_scene_div.text.strip()
        if '渑池' != city_scene_name:
            self.user_logger.error(f'{self.name}: 无法前往渑池')
            return False
        self.user_logger.info(f'{self.name}: 已到达渑池')

        self.user_logger.info(f'{self.name}: 领取演武厅奖励')
        soup = self.command('演武厅')
        
        success = False
        # Find the reward td element
        all_tds = soup.find_all('td')
        for td in all_tds:
            # Look for the td containing "上次比武奖励"
            if '上次比武奖励' in td.get_text():
                # Check if reward has already been claimed (已领取)
                if '已领取' in td.get_text():
                    self.user_logger.info(f'{self.name}: 演武厅奖励已领取')
                    success = True
                    break
                
                # Find the onclick attribute with arena_get_prise
                onclick_link = td.find('a', onclick=re.compile(r'arena_get_prise'))
                if not onclick_link:
                    self.user_logger.info(f'{self.name}: 未找到可领取的演武厅奖励')
                    break
                
                # Extract reward_id from onclick="arena_get_prise ( '9_2_1760630400', '0' )"
                onclick_text = onclick_link.get('onclick', '')
                reward_id_match = re.search(r"arena_get_prise\s*\(\s*'([^']+)'", onclick_text)
                if not reward_id_match:
                    self.user_logger.error(f'{self.name}: 无法解析演武厅奖励ID')
                    break
                
                reward_id = reward_id_match.group(1)
                
                # Extract rank (e.g., "No.9")
                rank_match = re.search(r'No\.(\d+)', td.get_text())
                rank = rank_match.group(0) if rank_match else '未知'
                
                # Extract reputation/声望 (e.g., "+864")
                reputation_match = re.search(r'声望：.*?([+\-]?\d+)', td.get_text())
                reputation = reputation_match.group(1) if reputation_match else '0'
                
                # Extract coins/铜币 (e.g., "257,000")
                coins_match = re.search(r'奖励：.*?([\d,]+)\s*铜币', td.get_text())
                coins = coins_match.group(1) if coins_match else '0'
                
                self.user_logger.info(f'{self.name}: 演武厅奖励 - 排名: {rank}, 声望: {reputation}, 铜币: {coins}')
                self.user_logger.info(f'{self.name}: 正在领取演武厅奖励 (ID: {reward_id})')
                
                # Claim the reward using the command
                self.command('演武厅领奖', id=reward_id)
                self.user_logger.info(f'{self.name}: 演武厅奖励领取成功')
                success = True

        if not success:
            self.user_logger.info(f'{self.name}: 未找到演武厅奖励信息')

        if was_training or goback_training:
            self.user_logger.info(f'{self.name}: 回国都恢复训练')
            self.return_home_and_train(18)


    def get_dungeon_progress(self) -> tuple[int, tuple[str, str]]:
        soup = self.command('升级导航')
        # 寻找页面上的"今日已进入副本次数：2 / 2"类似文本
        # 一般在页面源码里直接找
        text = soup.get_text()
        m = re.search(r'今日已进入副本次数：[^\d]*(\d+)\s*/\s*\d+', text)
        first_count = int(m.group(1)) if m else 0

        # INSERT_YOUR_CODE
        # Also extract "副本保存进度：天堂瀑布 - 天堂瀑布海角壁" from the text, and store dungeon progress if found
        dungeon_saved_progress = None
        progress_match = re.search(r'副本保存进度：([^\s-]+)\s*-\s*([^\s]+)', text)
        if progress_match:
            # Store as a tuple: (main dungeon, sub location)
            dungeon_saved_progress = (progress_match.group(1), progress_match.group(2))
        return first_count, dungeon_saved_progress

    def return_home_and_train(self, hour: int = 12):
        self.user_logger.info(f'{self.name}: 回国都并训练{hour}小时')
        self.command('回国都')
        self.command('训练', id=hour)

    def return_home_and_recharge(self):
        self.user_logger.info(f'{self.name}: 回国都并客房补血')
        self.command('回国都')
        self.command('客房补血')

    def daily_gift(self):
        self.user_logger.info(f'{self.name}: 尝试领取每日豪礼')
        try:
            soup = self.command('每日豪礼')
            # 提取所有 famExploreEnter 的时间戳 ID，并逐个领取
            gifts = []
            # 通过 input 的 onclick 提取
            for inp in soup.find_all('input'):
                onclick = inp.get('onclick', '')
                m = re.search(r"famExploreEnter\s*\(\s*'(?P<id>\d+)'\s*\)", onclick)
                if m:
                    gid = m.group('id')
                    gname = inp.get('value', '') or gid
                    gifts.append((gid, gname))
            for gid, gname in gifts:
                # gname is date like "10月30日"，continue if it is after today
                today = get_china_now().strftime("%m月%d日")
                if gname > today:
                    continue
                ret = self.command('豪礼领取', id=gid)
                self.user_logger.info(f"{self.name}: 豪礼领取 - {gname} - {ret.get('result')}")
        except Exception as e:
            pass

        soup = self.command('每日好礼')
        if not soup:
            return

        # Check if page has the required trigger and that twoflag is '1'
        html = str(soup)
        has_fam_explore_enter = ('onclick="famExploreEnter' in html) or ('onclick=\"famExploreEnter' in html)
        match_oneflag = re.search(r"window\.oneflag\s*=\s*['\"]?(\d)['\"]?", html)
        free_gift_is_one = bool(match_oneflag and match_oneflag.group(1) == '1')

        if has_fam_explore_enter and free_gift_is_one:
            self.user_logger.info(f"{self.name}: 有免费每日好礼，执行领取")
            for i in range(3):
                try:
                    self.command('好礼领取')
                    time.sleep(2)
                    soup = self.command('查看领取')
                    self.user_logger.info(f"{self.name}: 每日好礼领取成功")
                    break
                except Exception as e:
                    continue

    def gold_gem(self):
        try:
            html = self.command('黄金宝石')
            if not html: return

            # match 本日剩余免费抽取次数： 2
            m = re.search(r'本日剩余免费抽取次数：\s*(\d+)', html)
            free_count = int(m.group(1)) if m else 0
            if free_count > 0:
                self.user_logger.info(f"{self.name}: 本日剩余免费抽取次数: {free_count}")
                for i in range(free_count):
                    html = self.command('宝石抽取')
                    if isinstance(html, dict) and html.get('error'):
                        self.user_logger.error(f'{self.name}: 抽取黄金宝石失败: {html.get('result')}')
                        return
                    self.user_logger.info(f"{self.name}: 抽取黄金宝石成功")
                    m = re.search(r'本日剩余免费抽取次数：\s*(\d+)', html)
                    free_count = int(m.group(1)) if m else 0
                    if free_count == 0: break

        except Exception as e:
            self.user_logger.error(f'{self.name}: 抽取黄金宝石失败: {e}')

    def duel_trial(self):
        soup = self.command('竞速模式', is_duel_command=True)
        # Match "今天已发起挑战：<span class=highlight>1/2</span>"
        text_node = soup.find(string=re.compile('今天已发起挑战：'))
        if text_node:
            span = text_node.find_next('span', class_='highlight')
            if span:
                challenge_text = span.text.strip()  # "1/2"
                current, max_total = map(int, challenge_text.split('/'))
                if current < max_total:
                    self.user_logger.info(f'{self.name}: 今天已发起挑战：{current}/{max_total}')
                    if current % 2 != 0:
                        soup = self.command('生存模式', is_duel_command=True)

                    boss_soup = self.command('BOSS模式', is_duel_command=True)
                    if boss_soup.find('img', onclick=re.compile(r'view_trail_boss')):
                        soup = boss_soup
                    # Find img tag with onclick="view_trail_boss( 44 );"
                    img_tag = soup.find('img', onclick=re.compile(r'view_trail_boss'))
                    if img_tag:
                        onclick = img_tag.get('onclick', '')
                        m = re.search(r'view_trail_boss\s*\(\s*(\d+)\s*\)', onclick)
                        if m:
                            boss_id = int(m.group(1))
                            self.user_logger.info(f'{self.name}: 挑战{"BOSS" if boss_soup else ("生存" if current % 2 != 0 else "竞速")}模式boss: {boss_id}')
                            self.command('流星阁战斗', id=boss_id, is_duel_command=True)

    def olympics(self, type: str):
        olympics_command_links = {
            '职业赛':     ('/modules/olympics.php?act=add&callback_func_name=callbackRefreshOlympics', 'duel'),
            '单人赛':     ('/modules/server_arean.php?act=sign&id=1&callback_func_name=ajaxCallback', ''),
            '多人赛':     ('/modules/server_arean.php?act=sign&id=2&callback_func_name=ajaxCallback', ''),
            '乱战赛':     ('/modules/server_arean.php?act=sign&id=3&callback_func_name=ajaxCallback', ''),
            '纵横':       ('/modules/war.php?action=sign&type=1&callback_func_name=ajaxCallback&callback_obj_name=content', 'duel'),
        }
        command_link_tuple = olympics_command_links.get(type)
        if not command_link_tuple:
            self.user_logger.error(f'{self.name}: 未设置赛事: {type}')
            return

        command_link = command_link_tuple[0]
        command_type = command_link_tuple[1]
        return self.command(link=command_link, is_duel_command=(command_type == 'duel'))


    def sea_challange(self):
        try:
            ret = self.command('怒海争锋')
            if isinstance(ret, dict) and ret.get('error'):
                self.user_logger.info(f'{self.name}: 未解锁怒海争锋')
                return

            self.get_info()
            scene_map = {'初探流域': 1, "江河争霸": 2, "白衣渡江": 3, '水淹七军': 4, '赤壁之战': 5}
            current_scene = '初探流域'
            
            soup = self.command('怒海训练营')
            if not soup: return
            
            # Find training score: look for span with red color after "训练积分：" label
            label = soup.find(string=re.compile('训练积分：'))
            if not label:
                raise Exception(f'{self.name}: 未找到怒海训练营训练积分标签')
            
            red_span = label.parent.find_next_sibling('span', style=re.compile(r'color:\s*red', re.IGNORECASE))
            if not red_span:
                red_span = soup.find('span', style=re.compile(r'color:\s*red', re.IGNORECASE))
            if not red_span:
                raise Exception(f'{self.name}: 未找到怒海训练营训练积分数值')
            
            training_score = int(red_span.text.strip().replace(',', ''))
            self.user_logger.info(f"{self.name}: 怒海训练营训练积分: {training_score}")
            
            if training_score >= 100:
                self.user_logger.info(f"{self.name}: 训练营积分{training_score}，升级怒海训练营和船坞")
                while training_score >= 100:
                    self.command('训练营升级')
                    self.command('船坞升级')
                    training_score -= 100

            self.user_logger.info(f"{self.name}: 挑战怒海海战")
            # self.command('生成海战')
            ret = self.command('海战列表', id=scene_map[current_scene])
            if not ret:
                raise Exception(f'找不到海战列表')
            level = ret.find('div', class_='dlg_title').text.strip()
            # level is like "第10关"
            level = int(level.split('第')[1].split('关')[0])
            if level == 0:
                raise Exception(f'找不到海战关卡')

            while True:
                ret = self.command('海战挑战', id=level)
                combat_id = ret.get('combatId', 0)
                if combat_id == 0:
                    time.sleep(5)
                    continue

                win = wait_for_battle_completion(self.command, self.name, combat_id, self.user_logger, wait_for_completion=False)
                self.user_logger.info(f'{self.name}: 挑战第{level}关 {'成功' if win else '失败'}')
                if win:
                    level += 1 
                    time.sleep(5)             
                else:
                    break
        except Exception as e:
            self.user_logger.error(f'{self.name}: 挑战怒海海战失败: {e}')
    
    def buy_duel_medal(self, big_package: bool = True):
        soup = self.command('商城')
        
        # Find the script tag containing window.treasureItems
        script = soup.find('script', string=re.compile(r'window\.treasureItems'))
        if not script or not script.string:
            self.user_logger.error(f'{self.name}: 无法找到 window.treasureItems')
            return {"success": False, "message": f"无法找到 window.treasureItems"}
        
        script_content = script.string
        
        # Find the opening brace after window.treasureItems =
        start = script_content.find('window.treasureItems') + len('window.treasureItems')
        start = script_content.find('{', start)
        if start == -1:
            self.user_logger.error(f'{self.name}: 无法解析 window.treasureItems')
            return {"success": False, "message": f"无法解析 window.treasureItems"}
        
        # Find matching closing brace
        brace_count = 0
        for i in range(start, len(script_content)):
            if script_content[i] == '{':
                brace_count += 1
            elif script_content[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    json_str = script_content[start:i+1]
                    # Remove trailing commas before closing braces (common in JavaScript)
                    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
                    break
        else:
            self.user_logger.error(f'{self.name}: 无法解析 window.treasureItems')
            return {"success": False, "message": f"无法解析 window.treasureItems"}
        
        try:
            treasure_items = json.loads(json_str)
        except json.JSONDecodeError:
            self.user_logger.error(f'{self.name}: JSON 解析失败')
            return {"success": False, "message": f"JSON 解析失败"}

        if not treasure_items.get('66'):
            self.user_logger.error(f'{self.name}: 未找类别66 勋章战神令')
            return {"success": False, "message": f"未找到类别66 勋章战神令"}
        treasure_items = treasure_items['66']
        
        # Find the item with name "通用粉丝团勋章礼包(大)"
        target_name = "通用粉丝团徽章礼包(大)" if big_package else "通用粉丝团徽章礼包"
        for item in treasure_items:
            if isinstance(item, dict) and item.get('name') == target_name:
                item_id = item.get('item_id')
                
                # First call to get the payment form
                ret = self.command('商城购买', id=item_id)
                
                # Check if we got a payment form (errorContent indicates payment selection needed)
                if isinstance(ret, dict) and ret.get('errorContent'):
                    # Submit the purchase with 礼券支付 (mirror_money_type=1)
                    self.user_logger.info(f'{self.name}: 提交购买，使用礼券支付')
                    # Small delay to ensure server is ready
                    time.sleep(1)
                    post_data = {'mirror_money_type': '1'}
                    submit_ret = self.command.post('商城购买', data=post_data, id=item_id)
                    
                    if submit_ret.get('error'):
                        error_msg = submit_ret.get('result', submit_ret.get('error', '未知错误'))
                        self.user_logger.error(f'{self.name}: 购买{target_name}-{item_id}失败: {error_msg}')
                        return {"success": False, "message": f"购买{target_name}-{item_id}失败: {error_msg}"}
                    
                    self.user_logger.info(f'{self.name}: 购买{target_name}成功')
                    self.auto_gift()
                    return {"success": True, "message": f"购买{target_name}成功"}
        
        self.user_logger.error(f'{self.name}: 未找到物品 "{target_name}"')
        return {"success": False, "message": f"未找到物品 {target_name}"}
    
    def get_all_fan_badges(self):
        global fan_badges_cache
        if fan_badges_cache is not None:
            return fan_badges_cache
        
        soup = self.command('粉丝徽章')
        if not soup:
            return []
        
        badges = extract_fan_badges(soup)

        # Find the link with text "团队徽章2" and extract the type ID
        team_badge_link = soup.find('a', string='团队徽章2')
        if not team_badge_link:
            self.user_logger.error(f'{self.name}: 无法找到"团队徽章2"链接')
            return []
        
        # Extract type ID from onclick attribute
        # onclick format: "dialog.load ( '/modules/ore.php?type=254' );"
        onclick = team_badge_link.get('onclick', '')
        type_match = re.search(r'/modules/ore\.php\?type=(\d+)', onclick)
        if not type_match:
            self.user_logger.error(f'{self.name}: 无法从"团队徽章2"链接中提取type ID')
            return []
        
        type_id = type_match.group(1)
        self.user_logger.info(f'{self.name}: 找到团队徽章2 type ID: {type_id}')
        
        # Get the badge list using the type ID
        badge_soup = self.command('徽章类别', id=type_id)
        if not badge_soup:
            self.user_logger.error(f'{self.name}: 无法获取徽章列表')
            return []

        badges2 = extract_fan_badges(badge_soup) 
        badges.extend(badges2)
        fan_badges_cache = badges
        return badges

    def exchange_fan_badge(self, badge_name: str, badge_id: str, required_item: str, required_quantity: int, exchange_quantity: int):
        """
        Exchange fan badge with specified quantity.
        
        Args:
            badge_name: Name of the badge to exchange
            badge_id: ID of the badge to exchange
            required_item: Name of the required item
            required_quantity: Total quantity of required items needed
            exchange_quantity: Number of badges to exchange (1-100)
        """
        # Check if we have enough items

        total_quantity = required_quantity * exchange_quantity
        item_count = self.has_item(required_item)
        if item_count < total_quantity:
            total_quantity -= item_count
            item_count = self.has_item('通用粉丝团徽章')
            if item_count < total_quantity:
                self.user_logger.error(f'{self.name}: 还缺{total_quantity - item_count}个{required_item}或通用粉丝团徽章，无法兑换{badge_name}')
                return {"success": False, "message": f"还缺{total_quantity - item_count}个{required_item}或通用粉丝团徽章，无法兑换{badge_name}"}
            else:
                # Ensure fan_badges_cache is populated
                global fan_badges_cache
                if fan_badges_cache is None:
                    self.get_all_fan_badges()
                
                if fan_badges_cache is None:
                    self.user_logger.error(f'{self.name}: 无法获取粉丝徽章列表')
                    return {"success": False, "message": "无法获取粉丝徽章列表"}
                
                required_item_id = None
                for item in fan_badges_cache:
                    if required_item in item['name'] and item['required_item'] == '通用粉丝团徽章' and item['required_quantity'] == 1:
                        required_item_id = item['id']
                        break
                if not required_item_id:
                    self.user_logger.error(f'{self.name}: 未找到徽章 {required_item}')
                    return {"success": False, "message": f"未找到徽章 {required_item}"}
                self.user_logger.info(f'{self.name}: {required_item}不足，首先兑换{total_quantity}个通用粉丝团徽章')
                ret = self.command.exchange_reward(id=required_item_id, num=total_quantity)
                self.auto_gift()
        
        # Get the exchange form
        result = self.command.exchange_reward(id=badge_id, num=exchange_quantity)
        if result is None:
            self.user_logger.error(f'{self.name}: 徽章兑换提交返回空结果')
            return {"success": False, "message": "徽章兑换提交返回空结果"}
        
        if result.get('error', False):
            error_msg = result.get('result', '未知错误')
            self.user_logger.error(f'{self.name}: 徽章兑换失败: {error_msg}')
            return {"success": False, "message": f"徽章兑换失败: {error_msg}"}
        else:
            self.user_logger.info(f'{self.name}: 成功兑换 {exchange_quantity}个{badge_name}')
            self.auto_gift()
            return {"success": True, "message": f"成功兑换 {exchange_quantity}个{badge_name}"}

    def confidante_explore(self):
        try:
            soup = self.command('寻访页面')
            if isinstance(soup, dict) and soup.get('error'):
                self.user_logger.error(f'{self.name}: 寻访失败: {soup.get('result')}')
                return soup.get('result')
            
            # Find the menu container
            menu_ul = soup.find('ul', id='switch_menu_country')
            if not menu_ul:
                self.user_logger.warning(f'{self.name}: 未找到寻访页面')
                return None
            
            # Extract all link types and their select_type values
            links = []
            for li in menu_ul.find_all('li'):
                a_tag = li.find('a')
                if not a_tag:
                    continue
                
                link_text = a_tag.get_text(strip=True)
                onclick = a_tag.get('onclick', '')
                
                # Extract select_type from onclick attribute
                # Format: "process.start (); dialog.open ( '/modules/confidante.php?act=xun&select_type=1763136000', 'dlg_confidante_xun' )"
                match = re.search(r'select_type=(\d+)', onclick)
                if match:
                    select_type = match.group(1)
                    links.append({
                        'type': link_text,
                        'select_type': select_type
                    })

            answers = {
                '绝代佳人': 0,
                '才貌双全': 1,
                '倾国倾城': 0,
            }

            if not self.has_item('七彩灵石'):
                self.user_logger.info(f'{self.name}: 没有七彩灵石，荣誉兑换1个七彩灵石')
                self.command('荣誉兑换', id=f'{荣誉兑换列表['七彩灵石']}&itemNum=1')

            for link in links:
                answer = answers.get(link['type'])
                if answer is not None:
                    self.command('寻访', id=f'{link['select_type']}&answer={answer}')
                    self.user_logger.info(f'{self.name}: 寻访{link['type']} 答案{answer} 完成')
        
        except Exception as e:
            self.user_logger.error(f'{self.name}: 寻访失败: {e}')

    def guessroom_free_gift(self):
        soup = self.command('客房查看')
        if not soup:
            return None
        
        # Check if soup has guestroom_restore_free_moon_cake onclick and extract ID
        gift_links = soup.find_all('a', onclick=re.compile(r'guestroom_restore_free_moon_cake'))
        if gift_links:
            # Extract ID from onclick="guestroom_restore_free_moon_cake( '11', '客房有礼' )"
            for link in gift_links:
                onclick = link.get('onclick', '')
                match = re.search(r"guestroom_restore_free_moon_cake\s*\(\s*['\"]?(\d+)['\"]?", onclick)
                if match:
                    gift_id = match.group(1)
                    restore_link = '/modules/warrior.php?act=guestroom&op=restore&callback_func_name=warrior_common_callback&id='
                    self.user_logger.info(f'{self.name}: 领取免费客房有礼: {gift_id}')
                    self.command(link=f'{restore_link}{gift_id}')

    def distribute_team_energy(self):
        try:
            soup = self.command('我的武馆')
            if not soup:
                self.user_logger.warning(f'{self.name}: 无法获取我的武馆页面')
                return None
            
            # Extract team id from onclick="dialog.close(); fnEnterTeamScene( 3100 , 1 , 0);"
            team_id = None
            for link in soup.find_all('a', onclick=True):
                onclick = link.get('onclick', '')
                match = re.search(r'fnEnterTeamScene\s*\(\s*(\d+)', onclick)
                if match:
                    team_id = match.group(1)
                    break
            
            if not team_id:
                self.user_logger.warning(f'{self.name}: 无法从我的武馆页面提取团队ID')
                return None
            
            self.user_logger.info(f'{self.name}: 提取到团队ID: {team_id}')
            
            # Get energy from 武馆经验 command
            soup = self.command('武馆经验', id=team_id)
            if not soup:
                self.user_logger.warning(f'{self.name}: 无法获取武馆经验页面')
                return None
            
            # Extract energy from <strong>...累积囤积经验:<font class="highlight">25,852,300</font></strong>
            energy = None
            # Find the strong tag containing "累积囤积经验"
            for strong_tag in soup.find_all('strong'):
                text = strong_tag.get_text()
                if '累积囤积经验' in text:
                    highlight_font = strong_tag.find('font', class_='highlight')
                    if highlight_font:
                        energy_text = highlight_font.text.strip()
                        # Remove commas and convert to int
                        energy = int(energy_text.replace(',', ''))
                        break
            
            if energy is None:
                self.user_logger.warning(f'{self.name}: 无法从武馆经验页面提取经验值')
                return None
            
            self.user_logger.info(f'{self.name}: 武馆累积囤积经验: {energy:,}')
            
            # If energy > 23000000, call 经验分配 with POST
            if energy > 23000000:
                self.user_logger.info(f'{self.name}: 经验值 {energy:,} > 23,000,000，执行经验分配')
                result = self.command.post('经验分配', data={})
                if result and not result.get('error', False):
                    self.user_logger.info(f'{self.name}: 经验分配成功')
                else:
                    error_msg = result.get('result', '未知错误') if result else '返回空结果'
                    self.user_logger.error(f'{self.name}: 经验分配失败: {error_msg}')
            
            return energy

        except Exception as e:
            self.user_logger.error(f'{self.name}: 经验分配失败: {e}')
            return None

    def dragon_rank(self):

        failed_opponents = []
        while True:
            soup = self.command('化龙榜', is_duel_command=True)
            
            # Extract current rank from: <td>当前排名：<span class="highlight"><span class="small_font">750</span></span>
            rank = None
            rank_text_node = soup.find(string=re.compile('当前排名：'))
            if rank_text_node:
                rank_td = rank_text_node.find_parent('td')
                if rank_td:
                    small_font_span = rank_td.find('span', class_='small_font')
                    if small_font_span:
                        rank_text = small_font_span.text.strip()
                        # Check if rank is ">1000"
                        if rank_text == ">1000":
                            self.user_logger.info(f'{self.name}: 当前排名 >1000，不满足挑战条件')
                            return
                        try:
                            rank = int(rank_text)
                        except ValueError:
                            self.user_logger.warning(f'{self.name}: 无法解析排名: {rank_text}')
                            return
            if not rank:
                self.user_logger.warning(f'{self.name}: 无法提取排名')
                return

            # find CD time: if duelCombatDelay exists, extract 67 seconds from 
            # "duelCombatDelay.init ( 'server_duel_combat_delay', 67, 'fnCanHallServerDuelCombat' );"
            # if not CD is 0
            cd_time = 0
            duel_combat_delay = soup.find('script', string=re.compile('duelCombatDelay.init'))
            if duel_combat_delay:
                match = re.search(r'duelCombatDelay\.init\s*\(\s*[\'"]server_duel_combat_delay[\'"]\s*,\s*(\d+)\s*,\s*[\'"]fnCanHallServerDuelCombat[\'"]\s*\);', duel_combat_delay.string)
                if match:
                    cd_time = int(match.group(1))
            else:
                cd_time = 0
            
            # Extract challenge count from: <td>今日挑战次数：<span class="highlight">0 / 15</span>
            challenge_count = None
            count_text_node = soup.find(string=re.compile('今日挑战次数：'))
            if count_text_node:
                count_td = count_text_node.find_parent('td')
                if count_td:
                    highlight_span = count_td.find('span', class_='highlight')
                    if highlight_span:
                        count_text = highlight_span.text.strip()
                        # Extract "0 / 15" -> current is 0, max is 15
                        match = re.search(r'(\d+)\s*/\s*(\d+)', count_text)
                        if match:
                            challenge_count = int(match.group(1))
                            max_count = int(match.group(2))
                            self.user_logger.info(f'{self.name}: 当前排名: {rank}, 今日挑战次数: {challenge_count}/{max_count}')
            
            # Check eligibility: rank is not ">1000" and count < 15
            if challenge_count is None:
                self.user_logger.warning(f'{self.name}: 无法提取挑战次数')
                return
            
            if challenge_count >= 15:
                self.user_logger.info(f'{self.name}: 今日挑战次数已满 ({challenge_count}/15)')
                return
            
            self.user_logger.info(f'{self.name}: 等待CD时间: {cd_time}秒')
            time.sleep(cd_time)

            # Extract candidates and find one not in failed_opponents
            # Find all <div class="duel_rank"> elements
            candidate_rank = None
            candidate_name = None
            
            all_duel_rank_divs = soup.find_all('div', class_='duel_rank')
            for duel_rank_div in all_duel_rank_divs:
                rank_text = duel_rank_div.text.strip()
                try:
                    temp_rank = int(rank_text)
                except ValueError:
                    continue
                
                # Find the candidate name from the same parent div structure
                # The structure is: each candidate has its own container div that contains
                # both the duel_rank div and the name <a> tag
                # We need to find the immediate parent container that has both
                candidate_container = None
                # Walk up the parent tree to find the container div that contains both
                parent = duel_rank_div.parent
                while parent:
                    # Check if this parent contains an <a> tag with titlecontent
                    name_link = parent.find('a', attrs={'titlecontent': True})
                    if name_link:
                        candidate_container = parent
                        break
                    parent = parent.parent
                    # Stop if we've gone too far up (reached role_equip container)
                    if parent and parent.get('class') and 'role_equip' in parent.get('class'):
                        break
                
                if not candidate_container:
                    continue
                    
                name_link = candidate_container.find('a', attrs={'titlecontent': True})
                if not name_link:
                    continue
                    
                temp_name = name_link.get('titlecontent', '').strip()
                
                # Skip if this candidate is in failed_opponents
                if temp_name in failed_opponents:
                    self.user_logger.info(f'{self.name}: 跳过失败过的对手 - {temp_name}')
                    continue
                
                # Found a valid candidate not in failed_opponents
                candidate_rank = temp_rank
                candidate_name = temp_name
                break
            
            if candidate_rank is None or candidate_name is None:
                self.user_logger.warning(f'{self.name}: 无法找到可挑战目标（已跳过 {len(failed_opponents)} 个失败过的对手), 重新开始')
                failed_opponents = []
                continue
            
            # Call command "化龙榜挑战" with id={rank}
            ret = self.command('化龙榜挑战', id=candidate_rank, is_duel_command=True)
            combat_id = ret.get('success', 0)
            if combat_id:
                win = wait_for_battle_completion(self.command, self.name, combat_id, self.user_logger, wait_for_completion=False, is_duel_command=True)
                if not win:
                    failed_opponents.append(candidate_name)
                self.user_logger.info(f'{self.name}: 发起化龙榜挑战 - {candidate_name} (排名: {candidate_rank}) 结果: {"成功" if win else "失败"}')
            else:
                self.user_logger.warning(f'{self.name}: {ret.get('result', '未知错误')}')
                if '化龙榜战斗已經結束' in ret.get('result', ''):
                    return
                time.sleep(2)

    def zongheng_challenge(self):
        soup = self.command('纵横天下', is_duel_command=True)
        if not soup:
            return None
        
        # Extract location information from soup
        locations = []
        for link in soup.find_all('a', onclick=True, class_='active'):
            onclick = link.get('onclick', '')
            # Extract id from enterField(X)
            match = re.search(r'enterField\s*\(\s*(\d+)\s*\)', onclick)
            if match:
                location_id = int(match.group(1))
                location_name = link.text.strip()
                titlecontent = link.get('titlecontent', '').strip()
                is_active = 'active' in link.get('class', [])
                
                locations.append({
                    'id': location_id,
                    'name': location_name,
                    'titlecontent': titlecontent,
                    'active': is_active
                })

        if not locations:
            self.user_logger.warning(f'{self.name}: 纵横天下还未开启')
            return '纵横天下还未开启'

        defult_location = '军械库'
        defult_location_id = None
        for location in locations:
            if location['name'] == defult_location:
                defult_location_id = location['id']
                break
        if not defult_location_id:
            self.user_logger.warning(f'{self.name}: 未找到{defult_location}的ID')
            return '未找到{defult_location}的ID'

        ret = self.command('纵横进入战场', id=defult_location_id, is_duel_command=True)
        if not ret:
            self.user_logger.warning(f'{self.name}: 进入战场失败')
            return '进入战场失败'

        while True:
            ret = self.command('纵横天下刷新', is_duel_command=True)
            if not ret:
                self.user_logger.warning(f'{self.name}: 刷新战场失败')
                time.sleep(2)
                continue

            if ret.get('deadFightWait', 0) == 0 and ret.get('warFightWait', 0) == 0:
                combat_ret = self.command('纵横天下战斗', is_duel_command=True)
                if combat_ret.get('error', False):
                    message = combat_ret.get('result')
                    if '不处于交战状态' in message:
                        self.user_logger.info(f'{self.name}: 纵横天下战斗已经结束')
                        return '纵横天下战斗已经结束'
                    time.sleep(20)
                elif combat_ret.get('success', False):
                    warCombatDelay = combat_ret.get('warCombatDelay', 0)
                    waitWarFight = combat_ret.get('waitWarFight', 0)
                    time.sleep(warCombatDelay)
