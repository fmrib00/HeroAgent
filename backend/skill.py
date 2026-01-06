from typing import List, Dict, Tuple, Set
import re, json

skill_map = {
    '力破千钧0天':      '4015',
    '力破千钧0地':      '4016',
    '力破千钧0人':      '4017',
    '飞龙枪法0天':      '4003',
    '飞龙枪法0地':      '4004',
    '飞龙枪法0人':      '4005',
    '六合枪法0天':      '4009',
    '六合枪法0地':      '4010',
    '六合枪法0人':      '4011',
    '残红欲尽0天':      '4012',
    '残红欲尽0地':      '4013',
    '残红欲尽0人':      '4014',
    '暴麟逆走0天':      '4018',
    '暴麟逆走0地':      '4019',
    '暴麟逆走0人':      '4020',

    '伏虎势':           ('6', '53'),    # 6: skill_id, 53: state_id
    '裂马势':           ('124', '91'),  # 124: skill_id, 91: state_id

    '亢龙枪法':         '18',
    '破风枪法0天':      '4021',
    '破风枪法0地':      '4022',
    '破风枪法0人':      '4023',
    '怒蛟枪法0天':      '4027',
    '怒蛟枪法0地':      '4028',
    '怒蛟枪法0人':      '4029',
    '龙卷枪法0天':      '4030',
    '龙卷枪法0地':      '4031',
    '龙卷枪法0人':      '4032',
    '鹰击长空0天':      '4036',
    '鹰击长空0地':      '4037',
    '鹰击长空0人':      '4038',
    '血炎焚身0天':      '4039',
    '血炎焚身0地':      '4040',
    '血炎焚身0人':      '4041',
    
    '物换星移':         ('19', '37'),
    '金刚不坏':         ('20', '26'),
    '霸者横栏':         ('127', '84'),
    '九龙护体':         ('184', '264'),

    '斩玄剑法0天':      '4042',
    '斩玄剑法0人':      '4044',
    '补遗剑法0人':      '4050',
    '魅影剑法0天':      '4051',
    '魅影剑法0人':      '4053',
    '戮血剑法0人':      '4062',

    '举鼎式':           ('27', '14'),
    '腾挪式':           ('28', '15'),
    '顶天式':           ('31', '31'),
    '破天式':           ('32', '32'),

    '定身式0人':        '4089',
    '破甲式0天':        '4090',
    '破甲式0地':        '4091',
    '破甲式0人':        '4092',
    '卸武式0天':        '4093',
    '卸武式0人':        '4095',
    '穿心0天':          '4096',
    '截脉0天':          '4102',
    '截脉0人':          '4104',

    '邪恶战意':         ('53', '65'),
    '灭情战意':         ('54', '66'),
    '心眼式':           ('135', '88'),
    '蚀蛊式':           ('187', '267'),
    '怒澜式':           ('188', '269'),

    '追影式0天':        '4105',
    '追影式0地':        '4106',
    '追影式0人':        '4107',
    '无命0天':          '4120',
    '无命0地':          '4121',
    '无命0人':          '4122',
    '分身0天':          '4123',
    '分身0地':          '4124',
    '分身0人':          '4125',

    '绝情战意':         ('64', '16'),
    '残杀战意':         ('65', '22'),
    '断义战意':         ('66', '17'),
    '心水战意':         ('189', '270'),
    '残匕战意':         ('190', '271'),

    '无我剑气0天':      '4075',
    '无我剑气0地':      '4076',
    '无我剑气0人':      '4077',
    '缚神剑法0天':      '4081',
    '缚神剑法0地':      '4082',
    '缚神剑法0人':      '4083',

    '冰心剑诀':         ('43', '6'),
    '心静通灵':         ('39', '56'),
}

def skill_id_to_name(skill_id: str) -> str:
    for name, id in skill_map.items():
        if isinstance(id, tuple):
            if id[1] == skill_id:
                return name
        else:
            if id == skill_id:
                return name

    return None

def extract_main_skill(wbdata: str) -> str:
    match = re.search(r'"equiped_skill_id"\s*:\s*"(\d+)"', wbdata)
    return skill_id_to_name(match.group(1))

def extract_auxiliary_skill(wbdata: str) -> Set[str]:
    '''Get auxiliary skill from server'''

    # get auxiliary skill
    match = re.search(r'window\.roleStates\s*=\s*({.*?});', wbdata)
    if not match: return set()
    
    states = json.loads(match.group(1))
    auxiliary_skill = set()
    for key in states:
        for _k, _v in skill_map.items():
            if isinstance(_v, tuple) and key == _v[1]:
                auxiliary_skill.add(_k)
    return auxiliary_skill

def aux_skill_state_id(skill: str) -> None:
    if skill not in skill_map:
        raise Exception(f'Unknown skill {skill}')

    if not isinstance(skill_map[skill], tuple):
        raise Exception(f'{skill} is not an auxiliary skill')
    
    return skill_map[skill][1]

def get_skill_id(skill: str) -> None:
    if skill not in skill_map:
        raise Exception(f'Unknown skill {skill}')

    skill_id = skill_map[skill]

    # if skill is a tuple, it means it is auxiliary skill and has a state id
    aux = isinstance(skill_id, tuple)
    if aux: skill_id = skill_id[0]

    return skill_id

