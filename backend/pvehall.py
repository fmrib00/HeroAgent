from typing import Optional
import re, json, time
from bs4 import BeautifulSoup
from datetime import datetime
from threading import Lock

from character import Character
from cache_utils import update_account_combat_counts
from skill import *

from log import logger

def is_user_stopped(username):
    """Check if a user has a global stop signal"""
    try:
        # Import here to avoid circular imports
        from main import user_stop_signals
        stopped = user_stop_signals.get(username, False)
        return stopped
    except ImportError:
        # If main module isn't available, return False
        return False

guard_data = {
    '封神异志':     ['申公豹', '陈桐', '王贵人', '黄飞虎', '胡喜媚', '哪吒', '李靖', '杨戬', '雷震子', '土行孙', '武吉', '散宜生',
                    '崇应彪', '纣王', '张凤', '陈梧', '黄滚', '风林', '张桂芳', '王魔', '杨森', '高友乾', '李兴霸', '魔礼海',
                    '魔礼红', '魔礼青', '魔礼寿', '碧霄', '琼霄', '云霄', '赵公明', '秦完', '赵江', '董全', '孙良', '张绍',
                    '白礼', '袁角', '姚宾', '金光圣母', '王变', '闻仲', '广目天王', '多闻天王', '增长天王', '持国天王', '碧霄娘娘', 
                    '云霄娘娘', '琼霄娘娘', '玄坛真君', '通天教主', '分水将军'
    ],

    '平倭群英传':   ['劫匪头目', '忍者头目', '浪人头目', '石原信男', '藤原恒次', '伊势鬼丸', '虎彻', '柳生宗近', '上忍才藏', '李光头',
                    '童子明', '王如龙', '吴惟忠', '李无咎', '陈大成', '丁茂', '千智子', '鸳鸯', '倭门次郎', '叶大正'
    ],

    '三国鼎立':     ['于禁', '张允', '曹洪', '夏侯惇', '曹仁', '马延', '乐进', '蔡瑁', '夏侯渊', '李典', '徐庶', '许褚', '鲁肃',
                    '张颌', '张飞', '夏侯恩', '赵云', '张昭', '孙权', '周瑜', '徐晃', '甘宁', '贾诩', '程昱', '张辽', '曹操',
                    '关羽', '黄忠', '刘备', '吕布', '满宠', '张飞', '赵云', '郭嘉', '姜维', '魏延', '司马懿', '关羽', '诸葛亮',
                    '吕布', '赵云', '甘宁', '关羽', '神张辽', '神曹操', '神诸葛亮', '神諸葛亮', '马超', '神司马懿', '神貂蝉', '魔·吕布'
    ],

    '乱世群雄':     ['蔺相如', '田单', '申不害', '春申君', '孟尝君', '信陵君', '平原君', '商鞅', '乐毅', '项燕', '司马错', '伍子婿',
                    '聂政', '乐羊', '孙膑', '孙武', '廉颇', '吕不韦', '豫让', '李牧', '王贲', '苏秦', '蒙恬', '王翦', '荆轲', '白起',
                    '李斯', '韩信', '秦始皇', '魔白起', '嬴政'
    ],

    '绝代风华':     ['步练师', '张春华', '妹喜', '卓文君', '骊姬', '甄姬', '虞姬', '黄月英', '王昭君', '蔡文姬', '褒姒', '吕雉',
                    '穆桂英', '赵飞燕', '杨玉环', '小乔', '芈月', '花木兰', '孙尚香', '貂蝉'],

    '武林群侠传':   ['岳灵姗', '向傲天', '林平芝', '左盟主', '岳怖群‌', '冲虚', '任莹莹', '任天行', '风清扬', '东方教主', '陈友谅', 
                    '宋青书', '灭绝', '周芷若', '成昆', '谢逊', '玄冥', '赵敏', '三丰', '无忌']
}

hall_data = {
    '封神异志':         '3',
    '平倭群英传':       '6',
    '武林群侠传':       '10',
    '三国鼎立':         '7',
    '乱世群雄':         '8',
    '绝代风华':         '9',
}

hall_skills = {
    '邪皇':     {
        'default':          ('破甲式0人', {'心眼式', '灭情战意'}),
        '三国鼎立':         {22: ('定身式0人', {'心眼式', '灭情战意'}),
                            23: ('定身式0人', {'心眼式', '灭情战意'}),
                            27: ('穿心0天', {'怒澜式', '蚀蛊式'}),
                            28: ('穿心0天', {'心眼式', '蚀蛊式'}),
                            29: ('截脉0人', {'心眼式', '灭情战意'}),
                            30: ('卸武式0天', {'怒澜式', '灭情战意'}),
                            31: ('截脉0人', {'心眼式', '灭情战意'}),
                            32: ('卸武式0人', {'怒澜式', '灭情战意'}),
                            35: ('定身式0人', {'心眼式', '灭情战意'}),
                            42: ('定身式0人', {'心眼式', '灭情战意'}),
                            45: ('卸武式0人', {'心眼式', '灭情战意'}),
                            46: ('截脉0天', {'心眼式', '灭情战意'}),
                            47: ('破甲式0人', {'心眼式', '灭情战意'}),
                            50: ('破甲式0天', {'心眼式', '灭情战意'}),
        },
        '乱世群雄':         {
                            7: ('卸武式0天', {'怒澜式', '灭情战意'}),
                            8: ('穿心0天', {'怒澜式', '蚀蛊式'}),
                            11: ('定身式0人', {'心眼式', '灭情战意'}),
                            13: ('破甲式0人', {'心眼式', '灭情战意'}),
                            17: ('破甲式0天', {'怒澜式', '灭情战意'}),
                            18: ('卸武式0天', {'心眼式', '灭情战意'}),
                            19: ('定身式0人', {'心眼式', '灭情战意'}),
                            20: ('卸武式0人', {'心眼式', '灭情战意'}),
                            21: ('卸武式0人', {'心眼式', '灭情战意'}),
                            25: ('定身式0人', {'心眼式', '灭情战意'}),
                            27: ('定身式0人', {'心眼式', '灭情战意'}),
                            28: ('破甲式0天', {'怒澜式', '灭情战意'}),
                            29: ('破甲式0天', {'怒澜式', '灭情战意'}),

        },
        '绝代风华':         {
                            5: ('破甲式0天', {'怒澜式', '灭情战意'}),
                            7: ('卸武式0天', {'怒澜式', '灭情战意'}),
                            8: ('定身式0人', {'心眼式', '灭情战意'}),
                            10: ('定身式0人', {'心眼式', '灭情战意'}),
                            14: ('破甲式0天', {'怒澜式', '灭情战意'}),
                            17: ('破甲式0天', {'怒澜式', '灭情战意'}),
                            18: ('截脉0人', {'怒澜式', '灭情战意'}),
                            19: ('定身式0人', {'心眼式', '灭情战意'}),
                            20: ('卸武式0人', {'怒澜式', '灭情战意'}),
                            21: ('卸武式0人', {'怒澜式', '灭情战意'}),
                            23: ('卸武式0人', {'怒澜式', '灭情战意'}),
        },
        '武林群侠传':       {
                            6: ('卸武式0人', {'怒澜式', '灭情战意'}),
        },
    },
    '武神':     {
        'default':          ('力破千钧0天', {'伏虎势'}),
        '三国鼎立':         {32: ('飞龙枪法0天', {'裂马势'}),
                            46: ('力破千钧0人', {'裂马势'}),
                            49: ('力破千钧0地', {'裂马势'}),
        },
        '乱世群雄':         {15: ('力破千钧0地', {'裂马势'}),
                            16: ('力破千钧0地', {'裂马势'}),
                            17: ('力破千钧0地', {'裂马势'}),
                            21: ('力破千钧0天', {'裂马势'}),
                            22: ('力破千钧0天', {'裂马势'}),
                            24: ('力破千钧0地', {'裂马势'}),
                            25: ('力破千钧0天', {'裂马势'}),
                            27: ('力破千钧0天', {'裂马势'}),
        },
        '绝代风华':         {10: ('力破千钧0天', {'裂马势'}),
        },
        '武林群侠传':       {}
    },
    '英豪':     {
        'default':          ('破风枪法0地', {'霸者横栏'}),
        '三国鼎立':         {7: ('龙卷枪法0人', {'霸者横栏'}),
                            8: ('血炎焚身0人', {'霸者横栏'}),
                            15: ('龙卷枪法0人', {'霸者横栏'}),
                            17: ('血炎焚身0人', {'霸者横栏'}),
                            18: ('龙卷枪法0人', {'霸者横栏'}),
                            21: ('血炎焚身0人', {'霸者横栏'}),
                            22: ('龙卷枪法0地', {'物换星移'}),
                            23: ('龙卷枪法0地', {'物换星移'}),
                            25: ('龙卷枪法0人', {'霸者横栏'}),
                            33: ('血炎焚身0人', {'霸者横栏'}),
                            34: ('龙卷枪法0人', {'霸者横栏'}),
                            35: ('龙卷枪法0地', {'物换星移'}),
                            36: ('龙卷枪法0人', {'霸者横栏'}),
                            37: ('破风枪法0人', {'霸者横栏'}),
                            38: ('龙卷枪法0人', {'霸者横栏'}),
                            39: ('龙卷枪法0地', {'物换星移'}),
                            40: ('龙卷枪法0人', {'霸者横栏'}),
                            41: ('血炎焚身0人', {'霸者横栏'}),
                            42: ('龙卷枪法0地', {'物换星移'}),
                            43: ('龙卷枪法0人', {'霸者横栏'}),
                            44: ('血炎焚身0人', {'金刚不坏'}),
                            45: ('血炎焚身0人', {'物换星移'}),
                            46: ('龙卷枪法0地', {'物换星移'}),
                            47: ('血炎焚身0人', {'金刚不坏'}),
                            49: ('龙卷枪法0人', {'霸者横栏'}),
                            50: ('血炎焚身0人', {'金刚不坏'}),
        },
        '乱世群雄':         {
                            1: ('龙卷枪法0人', {'物换星移'}),
                            5: ('血炎焚身0人', {'霸者横栏'}),
                            6: ('龙卷枪法0人', {'霸者横栏'}),
                            9: ('血炎焚身0人', {'霸者横栏'}),
                            10: ('血炎焚身0人', {'霸者横栏'}),
                            11: ('龙卷枪法0地', {'物换星移'}),
                            12: ('龙卷枪法0人', {'金刚不坏'}),
                            13: ('破风枪法0天', {'物换星移'}),
                            14: ('血炎焚身0人', {'霸者横栏'}),
                            16: ('龙卷枪法0人', {'霸者横栏'}),
                            17: ('龙卷枪法0人', {'金刚不坏'}),
                            19: ('破风枪法0天', {'金刚不坏'}),
                            20: ('破风枪法0天', {'金刚不坏'}),
                            21: ('龙卷枪法0人', {'金刚不坏'}),
                            22: ('血炎焚身0人', {'金刚不坏'}),
                            23: ('血炎焚身0人', {'霸者横栏'}),
                            24: ('龙卷枪法0人', {'金刚不坏'}),
        },
        '绝代风华':         {
                            1: ('龙卷枪法0人', {'霸者横栏'}),
                            3: ('破风枪法0人', {'霸者横栏'}),
                            4: ('破风枪法0人', {'霸者横栏'}),
                            5: ('龙卷枪法0人', {'金刚不坏'}),
                            9: ('血炎焚身0人', {'霸者横栏'})
        },
        '武林群侠传':       {
                            4: ('血炎焚身0人', {'霸者横栏'}),
                            5: ('血炎焚身0人', {'霸者横栏'}),
        },
    },
    '天煞':     {
        'default':          ('分身0人', {'绝情战意', '残杀战意'}),
        '三国鼎立':         {
        },
    },
    '剑尊':     {
        'default':          ('斩玄剑法0天', {'举鼎式', '破天式'}),
        '乱世群雄':         {
                            5: ('魅影剑法0天', {'举鼎式', '顶天式'}),
                            6: ('魅影剑法0天', {'举鼎式', '顶天式'}),
                            9: ('魅影剑法0天', {'举鼎式', '顶天式'}),
                            10: ('魅影剑法0天', {'举鼎式', '顶天式'}),
                            11: ('戮血剑法0人', {'举鼎式', '破天式'}),
                            19: ('斩玄剑法0人', {'举鼎式', '顶天式'}),
                            23: ('魅影剑法0天', {'举鼎式', '顶天式'}),
                            24: ('魅影剑法0天', {'举鼎式', '顶天式'}),
        },
        '绝代风华':         {
                            6: ('斩玄剑法0天', {'举鼎式', '顶天式'}),
                            9: ('魅影剑法0天', {'举鼎式', '顶天式'}),
        },
        '武林群侠传':       {
                            5: ('魅影剑法0天', {'举鼎式', '顶天式'}),
        },
    },
    '剑神':     {
        'default':          ('无我剑气0地', {'冰心剑诀', '心静通灵'}),
    },
}

def get_target_guard(soup: BeautifulSoup):
    targets = []

    matching_texts = soup.find_all(string=re.compile(r'进行挑战'))

    for matching_text in matching_texts:
        # Check if the parent is an <a> tag
        if matching_text.parent.name == 'a':
            # Extract the onclick attribute value
            onclick_value = matching_text.parent.get('onclick', '')

            # Use regular expression to extract the number
            match = re.search(r'view_pve\((\d+)', onclick_value)

            if match:
                monster_id = int(match.group(1))
                monster_type = 'NPC'      # NPC
                monster_span = matching_text.parent.parent.parent.find('span', class_='text_monster')
                if monster_span is None:
                    monster_span = matching_text.parent.parent.parent.find('span', class_='text_npc')
                else:
                    monster_type = '小怪' # Monster

                if monster_span is None:
                    monster_span = matching_text.parent.parent.parent.find('span')
                    if monster_span is None: continue
                    monster_type = 'other'

                monster_name = monster_span.text.strip()
                targets.append((monster_id, monster_name, monster_type))

    return targets

class PVEHall():
    def __init__(self, character: Character, config: dict, user_logger=None) -> None:
        # Thread.__init__(self)
        self.char = character
        self.name = self.char.name
        self.user_logger = user_logger or logger  # Use provided logger or fall back to global logger
        self.config = {}

        for hall in hall_data:
            if hall in config:
                setting = config[hall]
                # Skip this hall if setting is "跳过"
                if setting == "跳过":
                    self.user_logger.info(f'{self.name}: 跳过幻境 {hall}')
                    continue
                
                setting_splits = setting.split('|')
                self.config[hall] = {}

                for s in setting_splits:
                    if s != '':
                        split = s.split(':')
                        if len(split) < 2:
                            raise Exception(f'Invalid setting {s} for hall {hall}')
                        self.config[hall][int(split[0])] = split[1]
        self.user_logger.info(f'{self.name}: {self.config}')

        # Handle boolean settings with backward compatibility for integer values
        die_repeat_val = config.pop('复活重打', False)
        life_refill_val = config.pop('客房补血', False)
        buy_combat_val = config.pop('自动买次数', False)
        die_switch_val = config.pop('失败切换', False)
        
        # Convert to boolean, handling both boolean and integer legacy values
        self.die_repeat = bool(die_repeat_val)
        self.die_switch = bool(die_switch_val)
        self.life_refill = bool(life_refill_val)
        self.buy_combat = bool(buy_combat_val)
        
        self.user_logger.info(f'{self.name}: 复活重打: {self.die_repeat}, 失败切换: {self.die_switch}, 客房补血: {self.life_refill}, 自动买次数: {self.buy_combat}')

        self._stopped = False
        self._thread = None  # Store reference to the running thread
        self._thread_lock = Lock()  # Lock for thread reference operations
        self.username = None  # Store username for global stop checking
        
        # Initialize hall-related attributes to prevent AttributeError
        self.curr_hall = None
        self.curr_level = None
        self.current_guard = None
        self.inside_hall = False
        self.combat_count = 0
        self.total_combat_count = 0
        self.extra_combat_count = False
        self.combat_targets = []
        self.score = 0
    
    def _set_thread(self, thread):
        """Safely set the thread reference"""
        with self._thread_lock:
            self._thread = thread
    
    def _get_thread(self):
        """Safely get the thread reference"""
        with self._thread_lock:
            return self._thread
    
    def _clear_thread(self):
        """Safely clear the thread reference"""
        with self._thread_lock:
            self._thread = None
    
    def _is_stopped(self) -> bool:
        """Check if the hall should be stopped (local or global signal)"""
        if self._stopped:
            return True
        
        # Check global stop signal if username is available
        if self.username:
            global_stopped = is_user_stopped(self.username)
            return global_stopped
        
        return False

    def get_hall(self) -> Optional[str]:
        if self.current_guard:
            for name, guards in guard_data.items():
                if self.current_guard in guards:
                    return name
        return None

    def get_hall_info(self) -> None:
        try:
            soup = self.command('幻境塔')
            wbdata = str(soup)
        except Exception as e:
            if 'gzip' in str(e).lower() or 'decompress' in str(e).lower():
                self.user_logger.warning(f'{self.name}: Gzip解压错误，等待后重试: {e}')
                time.sleep(5)
                # Try one more time
                try:
                    soup = self.command('幻境塔')
                    wbdata = str(soup)
                except Exception as retry_e:
                    self.user_logger.error(f'{self.name}: 重试后仍然失败: {retry_e}')
                    raise
            else:
                raise

        element = soup.find('div', class_='npc_dlg_content')
        self.inside_hall = False if element is None else True
        self.current_guard = element.text.split('：')[0] if self.inside_hall else None

        self.curr_hall = self.get_hall()

        if self.inside_hall:
            if self.curr_hall is None:
                raise Exception(f'找不到幻境名称: 当前NPC {self.current_guard} 不在任何幻境中')
            
            match = re.search(r'您当前处于第\s*<span class="highlight">(\d+)</span>', wbdata)
            if match is None:
                raise Exception('找不到幻境层数')
            self.curr_level = int(match.group(1))

        match = re.search(r'本周挑战次数:\s*<span class=".*?">(\d+/\d+)</span>', wbdata)
        if match is None:
            raise Exception('找不到本周挑战次数')
        self.combat_count, self.total_combat_count = map(int, match.group(1).split('/'))

        # extra combat count is true when the available combat count is more than 60 before fighting '平倭群英传'
        # use this flag to decide whether to fight '平倭群英传' or not
        self.extra_combat_count = (self.total_combat_count - self.combat_count > 75) or self.total_combat_count > 110

        self.combat_targets = get_target_guard(soup)
        self.score = self.get_score()
       
    def __repr__(self) -> str:
        ret = ''
        if self.curr_hall:
            ret += f'PVEHall({self.curr_hall}, {self.current_guard}, level {self.curr_level}) - '
        ret += f'挑战次数：{self.combat_count}/{self.total_combat_count}'
        if self.curr_hall:
            ret += f'\n挑战目标：{self.combat_targets}'
        return ret
    
    def select_hall(self, hall: str) -> bool:
        self.user_logger.info(f'{self.name}: 尝试进入 {hall}')
        if hall not in hall_data:
            raise Exception(f'Invalid hall {hall}')
        
        if self.curr_hall is not None and hall != self.curr_hall:
            self.user_logger.info(f'{self.name}: 已经在 {self.curr_hall} 不能切换到 {hall}')
            return False
        
        if self.curr_hall is None:
            self.command('选择幻境塔', id=hall_data[hall])
            self.get_hall_info()
            return self.curr_hall == hall
        
        return True

    def process_error(self, target: tuple, result: dict) -> bool:
        self.user_logger.info(f'{self.name}: 战斗失败 {target[1]}: {result["result"]}')
        if '在战斗中' in result['result']:
            time.sleep(5)
            # Return True to retry the same combat
            return True
        
        if '在战斗结束 5' in result['result'] or '操作过于频繁' in result['result']:
            # Return True to retry the same combat after waiting
            time.sleep(4)
            return True
        
        if '此人已死' in result['result']:
            # When target is already dead, we should advance to next level
            # Return False to stop current combat and let the main loop handle level advancement
            self.user_logger.info(f'{self.name}: 目标已死亡，跳过当前层数')
            return True
        
        if '幻境塔乃神秘凶险之地' in result['result']:
            self.command('离开武馆')
            self.user_logger.info(f'{self.name}: 离开武馆')
            return True
        
        if '你已经死亡' in result['result']:
            if target[2] == 'R':    # 复活重打
                self.command('复活')
                return True
        
        return False

    def combat_target(self, target: tuple, odd_life=False) -> bool:
        '''Combat a target(id, name, type), use odd_life to determine if need to set odd life point'''

        repeat = 3 if self.die_repeat else 0
        self.user_logger.info(f'{self.name}: 挑战目标：{self.curr_hall} (第{self.curr_level}层): {target[1:]}')
        with self.char.odd_life_context(odd_life):
            while repeat >= 0:
                # Check for stop signal before each attempt
                if self._is_stopped():
                    self.user_logger.info(f'{self.name}: 战斗已停止，退出挑战')
                    return False
                    
                target_id = target[0]
                ret = self.command('挑战幻境塔', id=target_id)
                if ret is None:
                    self.user_logger.info(f'{self.name}: 挑战 {target[1]} 失败')
                    return False

                if 'error' in ret:
                    ret = self.process_error(target, ret)
                    if repeat > 0: repeat -= 1
                    if ret: continue
                    return False

                combat_id = ret.get('success', 0)
                if combat_id == 0:
                    raise Exception(f'找不到{target[1]}的战斗ID')

                time.sleep(1)

                ret = self.command('战斗查看', id=combat_id)
                while '正在准备战斗，请稍候' in ret:
                    self.user_logger.info(f'{self.name}: 正在准备战斗，请稍候')
                    time.sleep(2)
                    try:
                        ret = self.command('战斗查看', id=combat_id)
                    except Exception as e:
                        if 'gzip' in str(e).lower() or 'decompress' in str(e).lower():
                            self.user_logger.warning(f'{self.name}: 战斗查看时Gzip解压错误，等待后重试: {e}')
                            time.sleep(3)
                            try:
                                ret = self.command('战斗查看', id=combat_id)
                            except Exception as retry_e:
                                self.user_logger.error(f'{self.name}: 重试后仍然失败: {retry_e}')
                                return False
                        else:
                            raise

                json_objects = re.findall(r'{"t".*?}', ret)

                # If there are matches, get the last one
                if not json_objects:
                    raise Exception(f'找不到战斗事件列表 {target[1]}')

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
                time.sleep(total_time)
                    
                if '你技高一筹，获得了胜利' in text:
                        self.user_logger.info(f'{self.name}: 挑战 {target[1]} 成功, 等待 {total_time:.1f} 秒')
                        return True
                else:
                    self.user_logger.info(f'{self.name}: 挑战 {target[1]} 失败, 等待 {total_time:.1f} 秒')
                    self.char.get_info()
                    if self.char.status == '死亡': self.command('复活')
                    repeat -= 1
                    if repeat >= 0:
                        self.user_logger.info(f'{self.name}: 复活重打')
                        continue
                    else:
                        if self.die_switch:
                            if self.combat_count + 4 < self.total_combat_count and self.curr_hall != '绝代风华':
                                self.user_logger.info(f'{self.name}: 退出并切换幻境，本周挑战次数：{self.combat_count}/{self.total_combat_count}')
                                self.command('幻境切换')
                            else:
                                self.user_logger.info(f'{self.name}: 本周挑战次数已用完，退出')
                        return False

    def combat(self, last_hall: bool) -> bool:
        '''looking at the current hall level to determine if to combat a target or to quit'''
        if self._is_stopped(): 
            self.user_logger.info(f'{self.name}: 战斗已停止')
            return False

        self.get_hall_info()
        if not self.combat_targets:
            return False
        
        # choose to target NPC or Monster according to config
        target_setting = self.config.get(self.curr_hall, {}).get(self.curr_level, 'NPC').split('!')
        self.user_logger.info(f'{self.name}: {self.curr_level}@{self.curr_hall} 挑战设置 {target_setting}')
        
        # Debug: Check if we're stuck on the same level
        if hasattr(self, '_last_combat_level') and self._last_combat_level == self.curr_level:
            self.user_logger.warning(f'{self.name}: 警告：仍在同一层 {self.curr_level}，可能存在循环问题')
        self._last_combat_level = self.curr_level
        target_type = 'NPC' if target_setting[0] == '' else target_setting[0]
        if len(target_setting) == 2:
            pattern = r"\(([^,]+),\s*\{([^}]*)\}\)"
            match = re.match(pattern, target_setting[1])
            main_skill = match.group(1)
            aux_skills = set(match.group(2).replace(' ', '').split(','))
        else:
            main_skill, aux_skills = self.default_skills
            if self.curr_hall in self.hall_skills:
                if self.curr_level in self.hall_skills[self.curr_hall]:
                    main_skill, aux_skills = self.hall_skills[self.curr_hall][self.curr_level]

        self.char.equip_main_skill(main_skill)

        self.char.equip_auxiliary_skill(aux_skills)
        if target_type == '退出':
            self.user_logger.info(f'{self.name}: 已到达 {self.curr_hall} 第 {self.curr_level} 层，退出')
            return False
        
        if target_type == '切换':
            # 次数用完，不自动买次数，退出
            # 次数没用完，或者自动买次数而且不是最后一塔，切换
            if self.combat_count + 1 <= self.total_combat_count and not last_hall:
                self.user_logger.info(f'{self.name}: 已到达 {self.curr_hall} 第 {self.curr_level} 层，退出并切换')
                self.command('幻境切换')
            else:
                self.user_logger.info(f'{self.name}: 已到达 {self.curr_hall} 第 {self.curr_level} 层，退出')
            return False
        
        odd_life = True if target_type == '奇数血' else False
        if target_type == '奇数血': target_type = 'NPC'

        if target_type == '小怪':
            self.user_logger.info(f'{self.name}: {self.curr_level}@{self.curr_hall} 设置挑战 小怪')
            
        self.user_logger.info(f'{self.name}: 本周挑战次数：{self.combat_count}/{self.total_combat_count}')
        if self.combat_count == self.total_combat_count:
            self.user_logger.info(f'{self.name}: 本周挑战次数已用完; 自动买次数: {self.buy_combat}')
            if self.buy_combat:
                self.command('幻境买次数')
                self.user_logger.info(f'{self.name}: 购买一次挑战次数')
            else:
                return False

        if target_type == '空蓝':
            self.user_logger.info(f'{self.name}: {self.curr_level}@{self.curr_hall} 设置空蓝挑战')
            self.char.empty_mana()
            target_type = 'NPC'

        for target in self.combat_targets:
            # Check for stop signal before each combat
            if self._is_stopped():
                self.user_logger.info(f'{self.name}: 战斗已停止，跳过剩余目标')
                return False
                
            # first try to match npc name, than npc type
            if target[1] == target_type or target[2] == target_type:
                return self.combat_target(target, odd_life=odd_life)
            
        # when all targets are monsters, we combate the first one
        npc_found = any(target[2] == 'NPC' for target in self.combat_targets)
        if not npc_found:
            return self.combat_target(self.combat_targets[0], odd_life=odd_life)

        self.user_logger.info(f'{self.name}: 找不到挑战目标 {target_type} 在 {self.curr_level}@{self.curr_hall}')
        return False
    
    def combat_hall(self, last_hall: bool) -> None:
        '''combat a PVEHall, quit by combat returns False'''

        self.use_score('灵台清明:100000')
        count = 0
        while self.combat(last_hall):
            # Check for stop signal after each combat
            if self._is_stopped():
                self.user_logger.info(f'{self.name}: 战斗已停止，退出幻境挑战')
                break
                
            # Update hall info after each successful combat to get the new level
            self.get_hall_info()
            self.user_logger.info(f'{self.name}: 当前进度: {self.curr_hall} 第 {self.curr_level} 层')
            
            if self.life_refill:
                self.command('客房补血')
            if count % 10 == 0:
                self.user_logger.info(f'{self.name}: 修理所有装备')
                self.command('全部修理')

            count += 1
        self.user_logger.info(f'{self.name}: {self.curr_hall} 挑战结束')

    def get_score(self) -> int:
        try:
            soup = self.command('幻境商城')
            div = soup.find('span', id='self_pve_inte_num').text.strip().replace(',', '')
            return int(div)
        except Exception as e:
            if 'gzip' in str(e).lower() or 'decompress' in str(e).lower():
                self.user_logger.warning(f'{self.name}: 获取积分时Gzip解压错误，等待后重试: {e}')
                time.sleep(5)
                # Try one more time
                try:
                    soup = self.command('幻境商城')
                    div = soup.find('span', id='self_pve_inte_num').text.strip().replace(',', '')
                    return int(div)
                except Exception as retry_e:
                    self.user_logger.error(f'{self.name}: 重试后仍然失败: {retry_e}')
                    # Return a safe default value
                    return 0
            else:
                raise

    def use_score(self, setting: str) -> None:
        item_map = {
            '灵台清明': 11,
            '财运亨通': 22,
            '黑铁矿': 117,
        }

        try:
            command = '/modules/shop.php?act=pve&op=buy&&itemID='
            self.command(link=command, id=item_map['黑铁矿'])
            self.command(link=command, id=item_map['黑铁矿'])
            self.user_logger.info(f'{self.name}: 幻境积分购买2件黑铁矿')
            self.score -= 2 * 3000

            item, keep = setting.split(':') if setting else (None, None)
            if item is None: return
            score_to_use = self.score - int(keep)

            if item == '灵台清明' or item == '财运亨通':
                qty = score_to_use // 750
                if qty > 0:
                    self.user_logger.info(f'{self.name}: 购买 {qty} 件 {item} ')
                    self.command(link=command, id=f'{item_map[item]}&itemNum={qty}')
            else:
                self.user_logger.info(f'{self.name}: 不支持的幻境积分物品 {item}')
        except Exception as e:
            self.user_logger.error(f'{self.name}: 使用幻境积分物品失败: {e}')

    def run(self):
        self._stopped = False
        self.char.get_info()

        if self.char.career not in hall_skills:
            raise Exception(f'幻境技能中找不到 {self.char.career} 设置')

        self.command = self.char.command
        self.hall_skills = hall_skills[self.char.career]
        self.default_skills = self.hall_skills['default']
        if self.char.status == '死亡': self.command('复活')
        self.life_refill = False

        try:
            self.get_hall_info()
        except Exception as e:
            if 'gzip' in str(e).lower() or 'decompress' in str(e).lower():
                self.user_logger.error(f'{self.name}: 初始化时Gzip解压错误，无法继续: {e}')
                raise
            else:
                raise

        self.user_logger.info(f'{self.name}: 读取幻境存盘')
        try:
            self.command('幻境塔读盘')
            self.command('幻境领次数')
        except Exception as e:
            if 'gzip' in str(e).lower() or 'decompress' in str(e).lower():
                self.user_logger.error(f'{self.name}: 读取幻境存盘时Gzip解压错误: {e}')
                raise
            else:
                raise
        start_time = datetime.now()
        self.user_logger.info(f'{self.name}: 本周挑战次数：{self.combat_count}/{self.total_combat_count}')
        if self.combat_count == self.total_combat_count and not self.buy_combat:
            update_account_combat_counts(self.char.username, self.name, self.combat_count, self.total_combat_count)
            self.user_logger.info(f'{self.name}: 本周挑战次数已用完，退出')
            return
        self.user_logger.info(f'{self.name}: 开始幻境挑战')

        self.command.activate_beauty_card('激活吸血')

        self.char.equip_weapon()

        for hall, setting in self.config.items():
            # Check for stop signal before each hall
            if self._is_stopped():
                self.user_logger.info(f'{self.name}: 战斗已停止，跳过剩余幻境')
                break
                
            if self.select_hall(hall):
                self.combat_hall(last_hall = list(self.config.keys())[-1]==hall)
                if self._is_stopped(): break

                self.get_hall_info()
                if self.curr_hall is None: 
                    self.user_logger.info(f'{self.name}: 通关 {hall}')
                else:
                    break

        end_time = datetime.now()

        elapsed_time = end_time - start_time
        minutes, seconds = divmod(elapsed_time.total_seconds(), 60)

        update_account_combat_counts(self.char.username, self.name, self.combat_count, self.total_combat_count)
        self.user_logger.info(f"{self.name}: 本次挑战用时 {int(minutes)} 分钟 {int(seconds)} 秒钟")

    def terminate(self) -> None:
        """Terminate the hall combat process"""
        self.user_logger.info(f'{self.name}: 收到停止信号')
        self._stopped = True
        
        # Safely get the thread reference
        thread = self._get_thread()
        
        # If we have a thread reference, try to interrupt it
        if thread is not None and hasattr(thread, 'is_alive') and thread.is_alive():
            try:
                # Note: Python doesn't support thread interruption, but we can set the flag
                # The thread will check the flag and exit gracefully
                self.user_logger.info(f'{self.name}: 线程正在运行，等待线程自然退出')
                
                # Wait a bit for the thread to respond to the stop signal
                import time
                wait_time = 0
                max_wait = 5  # Wait up to 5 seconds
                while thread is not None and hasattr(thread, 'is_alive') and thread.is_alive() and wait_time < max_wait:
                    time.sleep(0.1)
                    wait_time += 0.1
                
                if thread is not None and hasattr(thread, 'is_alive') and thread.is_alive():
                    self.user_logger.warning(f'{self.name}: 线程未能在 {max_wait} 秒内停止，可能需要强制终止')
                else:
                    self.user_logger.info(f'{self.name}: 线程已成功停止')
                    
            except Exception as e:
                self.user_logger.error(f'{self.name}: 停止线程时出错: {e}')
        elif thread is None:
            self.user_logger.info(f'{self.name}: 没有活动的线程引用')
        else:
            self.user_logger.info(f'{self.name}: 线程引用无效或已结束')
        
        self.user_logger.info(f'{self.name}: 幻境挑战已停止')

