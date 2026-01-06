from typing import Any, Callable
import requests, re, json
from bs4 import BeautifulSoup
import time
import urllib3.exceptions

# Request configuration
DEFAULT_REQUEST_TIMEOUT = 120
RETRY_DELAY_SECONDS = 3
MAX_RETRIES = 3


def retry_on_connection_error(request_func: Callable, role: str, max_retries: int = MAX_RETRIES):
    """
    Retry a request function on connection errors with exponential backoff.

    Args:
        request_func: The request function to execute (should return response object)
        role: The role name for logging purposes
        max_retries: Maximum number of retry attempts

    Returns:
        The response object from the request function

    Raises:
        Exception: If all retry attempts fail
    """
    retry_count = 0

    while retry_count < max_retries:
        try:
            return request_func()
        except (requests.exceptions.ConnectionError, urllib3.exceptions.ProtocolError) as e:
            # ProtocolError often wraps IncompleteRead errors from broken connections
            retry_count += 1
            if retry_count >= max_retries:
                raise Exception(f'{role}: 网络连接失败，已达到最大重试次数: {e}')
            time.sleep(RETRY_DELAY_SECONDS)
        except requests.exceptions.Timeout:
            retry_count += 1
            if retry_count >= max_retries:
                raise Exception(f'{role}: 请求超时，已达到最大重试次数')
            time.sleep(RETRY_DELAY_SECONDS)
        except requests.exceptions.ChunkedEncodingError as e:
            # Handle incomplete reads (chunked encoding errors)
            retry_count += 1
            if retry_count >= max_retries:
                raise Exception(f'{role}: 数据传输不完整，已达到最大重试次数: {e}')
            time.sleep(RETRY_DELAY_SECONDS)

    # Should never reach here, but just in case
    raise Exception(f'{role}: 请求失败，已达到最大重试次数')


command_links = {
    'home':            ('', 'soup'), # this is for homepage
    '角色信息':         ('/modules/role_info.php?&callback_func_name=callback_load_content%20&callback_obj_name=content', 'wbdata'),
    '角色属性':         ('/modules/role_info.php?act=attr&callback_func_name=ajaxCallback&callback_obj_name=role_attr', 'soup'),
    '全部修理':         ('/modules/role_item.php?act=repair_all_item&callback_func_name=itemClass.dragItemCallback', None),
    '复活':             ('/modules/revival.php?revival_type=1&callback_func_name=revival_callback', None),
    '离开武馆':         ('/modules/team.php?act=leave_team_scene&callback_func_name=callbackFnLeaveTeamScene', None),
    '药物补血':         ('/modules/role_item.php?act=drag_item&from=pack&to=none&op=use_to_role&callback_func_name=itemClass.dragItemCallback&id=', None),
    '客房补血':         ('/modules/warrior.php?act=guestroom&op=restore&id=1&callback_func_name=warrior_common_callback', None),
    '客房查看':         ('/modules/warrior.php?act=guestroom&callback_func_name=callback_load_content%20&callback_obj_name=content', 'soup'),

    '幻境切换':         ('/modules/duel.php?act=pvehall&action=change_pvehall&callback_func_name=ajaxCallback&mirror_money_type=1', None),
    
    '脱下装备':         ('/modules/role_item.php?act=drag_item&from=equip&to=pack&callback_func_name=itemClass.dragItemCallback&id=', None),
    '穿上装备':         ('/modules/role_item.php?act=drag_item&from=pack&to=equip&callback_func_name=itemClass.dragItemCallback&id=', None),
    '装备入包':         ('/modules/role_item.php?act=drag_item&from=temp&to=pack&callback_func_name=itemClass.dragItemCallback&id=', None),
    '出售临时包裹':     ('/modules/role_item.php?act=sell_all_temp', None),

    '技能内容':         ('/modules/role_skill.php?callback_func_name=callback_load_content%20&callback_obj_name=content', 'wbdata'),
    '装备技能':         ('/modules/role_skill.php?act=skill_equip&flag=undefined&equip_type=0&callback_func_name=role_skill_equip_callback&skill_id=', 'json'),
    '装备辅助技能':     ('/modules/role_skill.php?act=skill_use&callback_func_name=role_skill_use_callback&skill_id=', None),
    '移除辅助技能':     ('/modules/role_info.php?act=remove_state&state_id=', None),

    '幻境塔':           ('/modules/duel.php?act=pvehall&callback_func_name=callback_load_content%20&callback_obj_name=content', 'soup'),
    '幻境商城':         ('/modules/shop.php?act=pve&callback_func_name=ajaxCallback&callback_obj_name=dlg_shop', 'soup'),
    '挑战幻境塔':       ('/modules/duel.php?act=pvehall&action=fn&callback_func_name=callbackfnPveHallFight&pve_id=', 'json'),
    '战斗查看':         ('/modules/view_combat.php?start=0&callback_func_name=ajaxCallback&callback_obj_name=dlg_view_combat&combat_id=', 'wbdata'), 
    '选择幻境塔':       ('/modules/duel.php?act=pvehall&action=sType&callback_func_name=callBackSPveType&typeId=', None),
    '幻境塔读盘':       ('/modules/duel.php?act=pvehall&action=read_save_info&op=pay&callback_func_name=ajaxCallback', None),
    '幻境买次数':       ('/modules/duel.php?act=pvehall&action=buy_num&submit=1&in=&num=1&callback_func_name=ajaxCallback', None),
    '幻境领次数':       ('/modules/duel.php?act=pvehall&action=get_num&callback_func_name=ajaxCallback', None),

    '商城':             ('/modules/shop.php?act=treasure&type=7&callback_func_name=ajaxCallback&callback_obj_name=dlg_shop', 'soup'),
    '商城购买':         ('/modules/shop.php?act=treasure&action=buy&awards=1&item_id=', 'json'),

    '上装备':           ('/modules/role_item.php?act=drag_item&from=pack&to=equip&callback_func_name=itemClass.dragItemCallback&id=', None),
    '查看奴隶':         ('/modules/role_slavery.php?callback_func_name=ajaxCallback&callback_obj_name=dlg_sociality', 'wbdata'),
    '奴隶对象':         ('/modules/duel.php?act=slavery&callback_func_name=callback_load_content%20&callback_obj_name=content', 'soup'),
    '夺仆清单':         ('/modules/role_slavery.php?act=slaves_list&callback_func_name=ajaxCallback&callback_obj_name=dlg_view_slaves_list&boss_id=', 'soup'),
    '奴隶战斗':         ('/modules/slavery_fight.php?act=enemy_fight&is_reverse=2&callback_func_name=callbackFnSlaveryFight&capture_role_id=', 'json'),
    '折磨奴隶':         ('/modules/role_slavery.php?act=pain_list&type=1&action_id=0&scene_id=0&scene_type=0&callback_func_name=ajaxCallback&callback_obj_name=dlg_slave_opt_list&slave_id=', 'soup'),
    '折磨奴隶提交':     ('/modules/role_slavery.php?act=pain_submit', 'json'),
    '安抚奴隶':         ('/modules/role_slavery.php?act=comfort_list&type=2&callback_func_name=ajaxCallback&callback_obj_name=dlg_slave_opt_list&slave_id=', 'soup'),
    '安抚奴隶提交':     ('/modules/role_slavery.php?act=comfort_submit', 'json'),

    '包裹到铸造':       ('/modules/role_item.php?act=drag_item&from=pack&to=smithing&callback_func_name=itemClassBazaar.dragItemCallback&pos_x=0&pos_y=0&id=', None),
    '捐献':            ('/modules/role_item.php?act=donations_item&callback_func_name=itemClassBazaar.dragItemCallback', None),

    '签到查看':         ('/modules/day_weals.php?act=show&callback_func_name=ajaxCallback&callback_obj_name=dlg_view_weals', 'soup'),
    '签到':             ('/modules/day_weals.php?act=weal&&callback_func_name=callbackFnStartWeals', None),
    '福利查看':         ('/modules/day_weals_activity.php?act=show&callback_func_name=ajaxCallback&callback_obj_name=dlg_view_weals', 'soup'),
    '福利':             ('/modules/day_weals_activity.php?act=weal&id=1', None),
    '领辎重':           ('/modules/warrior.php?act=hall&op=war&speed_up=1', None),

    '竞技场':           ('/modules/inner_fun.php?act=ath_manage&op=show&callback_func_name=ajaxCallback&callback_obj_name=dlg_duel', 'soup'),
    '托管竞技场':       ('/modules/inner_fun.php?act=ath_manage&op=manage&callback_func_name=ajaxCallback', None),
    '竞技领奖':         ('/modules/inner_fun.php?act=ath_manage&op=getreward', None),
    '技能设置':         ('/modules/role_skill.php?act=equip_for_class&callback_func_name=ajaxCallback&callback_obj_name=dlg_equip_for_class', 'soup'),

    '任务':             ('/modules/role_mission.php?act=task_manage&function=day&op=show&callback_func_name=ajaxCallback&callback_obj_name=dlg_duel', 'soup'),
    '托管任务':         ('/modules/role_mission.php?act=task_manage&function=day&op=manage&type=1&callback_func_name=ajaxCallback', None),
    '任务领奖':         ('/modules/role_mission.php?act=task_manage&function=day&op=getreward&type=0&callback_func_name=ajaxCallback', None),

    '幻化':             ('/modules/displace.php?callback_func_name=callback_load_content%20&callback_obj_name=content', 'soup'),
    '幻化50次':         ('/modules/displace.php?act=get&type=4&callback_func_name=displace_call_back', None),
    '幻化10次':         ('/modules/displace.php?act=get&type=5&callback_func_name=displace_call_back', None),
    '冲锋陷阵':         ('/modules/diagrams.php?act=list&&callback_func_name=callback_load_content%20&callback_obj_name=content', 'soup'),
    '冲锋陷阵抽取':      ('/modules/diagrams.php?act=get&type=3&&callback_func_name=diagram_call_back', None),
    
    '战马':             ('/modules/horsees.php?act=list&callback_func_name=callback_load_content%20&callback_obj_name=content', 'soup'),
    '战马抽取':         ('/modules/horsees.php?act=get&type=1&callback_func_name=horse_call_back', None),
    '门客招募':         ('/modules/wisees.php?act=enter&select_type=1&callback_func_name=ajaxCallback&callback_obj_name=dialog1', None),
    '门客招募2':        ('/modules/wisees.php?act=view&select_type=1&callback_func_name=ajaxCallback&callback_obj_name=dialog0', None),
    '门客生成':         ('/modules/wisees.php?act=action&callback_func_name=ajaxCallback&callback_obj_name=dlg_wise_action', 'soup'),
    '门客挑战':         ('/modules/wisees.php?act=fight&callback_func_name=callbackWiseFight&boss_id=', None),

    '风云争霸':         ('/modules/server_duel_hall.php?callback_func_name=callback_load_content%20&callback_obj_name=content', 'soup'),
    '风云争霸挑战':     ('/modules/server_duel_fight.php?action=fight&callback_func_name=callbackFnServerDuelRoleFight&rid=', None),

    '训练':             ('/modules/warrior.php?act=hall&op=train&hours=', None),
    '终止训练':         ('/modules/warrior.php?act=hall&op=train&cancel=1', None),
    '授艺':             ('/modules/warrior.php?act=hall&op=work&hours=', None),
    '终止授艺':         ('/modules/warrior.php?act=hall&op=work&cancel=1', None),

    '礼包':             ('/modules/awards.php?callback_func_name=ajaxCallback&callback_obj_name=dlg_awards', 'soup'),
    '礼包领取':         ('/modules/awards.php?act=fetch&callback_func_name=awards_fetch_callback&award_id=', None),
    '整理包裹':         ('/modules/role_item.php?act=clear_up_item&type=pack&callback_func_name=itemClass.clearUpItemCallback', None),

    '怪物导航':         ('/modules/upgrade_help.php?act=practice&callback_func_name=ajaxCallback&callback_obj_name=dlg_view_practice', 'soup'),
    '移动场景':         ('/modules/scene_walk.php?action=scene_move&pk_status=0&callback_func_name=callbackFnMoveToScene&scene_id=', 'soup'),
    '刷新场景':         ('/modules/scene.php?callback_func_name=callback_load_stage%20&callback_obj_name=stage', 'soup'),
    '修炼':             ('/modules/auto_combats.php?act=show&callback_func_name=ajaxCallback&callback_obj_name=dlg_view_monster&mid=', 'soup'),
    '查看修炼':         ('/modules/auto_combats.php?act=view&callback_func_name=ajaxCallback&callback_obj_name=dlg_view_monster', 'soup'),
    '修炼提交':         ('/modules/auto_combats.php?act=start', 'soup'),
    '修炼立即完成':     ('/modules/auto_combats.php?act=complete&isfree=1&callback_func_name=callbackFnCancelAutoCombat', None),
    '打怪':             ('/modules/monster_fight.php?callback_func_name=callbackFnMonsterAction&mid=', 'json'),
    '回国都':           ('/modules/scenes_role.php?sid=0&callback_func_name=switch_scene_callback', None),
    '鉴定装备':         ('/modules/role_item.php?act=check_all_item&class=itemClass&check=1&callback_func_name=changAllItemCallback', None),

    '兑换奖励':         ('/modules/ore.php?submit=1&callback_func_name=ajaxCallback&num=1&id=', None),
    '贡献换铜币':       ('/modules/awards.php?act=get_mystery_award&reward_id=offer_reward_item&callback_func_name=get_mystery_award_callback&callback_obj_name=get_mystery_award', None),
    '荣誉兑换':         ('/modules/duel.php?act=glory&op=buy&itemID=', None),

    '前往渑池':         ('/modules/scene_walk.php?action=world_move&scene_id=164&callback_func_name=callbackFnWorldTransport', None),
    '演武厅':           ('/modules/warrior.php?act=arena&callback_func_name=callback_load_content%20&callback_obj_name=content', 'soup'),
    '演武厅领奖':       ('/modules/warrior.php?act=arena&op=get_prise&submit=1&team_mode=0&arena_key=', None),

    '武魂宝石查看':     ('/modules/soul.php?act=gem&op=show&soul_id=459&callback_func_name=ajaxCallback&callback_obj_name=dlg_soul_gem_gem', 'soup'),
    '武魂宝石抽取':     ('/modules/soul.php?act=gem&op=goldBatchPurple&soul_id=459&callback_func_name=ajaxCallback&callback_obj_name=dlg_soul_gem_gem', 'soup'),

    '美女图':          ('/modules/beauty.php?act=set_effect&callback_func_name=getBeautySetEffectCallback&set_id=', None),

    '地区冠军':         ('/modules/server_arean.php?type=province&act=getChampion&callback_func_name=ajaxCallback&callback_obj_name=show_server_arean_aw', None),
    '本服冠军':         ('/modules/server_arean.php?type=server&act=getChampion&callback_func_name=ajaxCallback&callback_obj_name=show_server_arean_aw', None),

    '进入大副本':       ('/modules/scene_walk.php?action=world_move&callback_func_name=callbackFnWorldTransport&scene_id=', 'json'),
    '副本场景':         ('/modules/scene_walk.php?action=walk&callback_func_name=callbackfnScene&sid=', 'json'),
    '查看副本入口':     ('/modules/scene_walk.php?action=enterThirdScene&pk_status=0&hide_tips=0&isfree=0&callback_func_name=callbackfnEnterThirdScene&sid=', 'json'),
    '进入副本入口':     ('/modules/scene_walk.php?action=enterThirdScene&pk_status=0&hide_tips=1&isfree=0&callback_func_name=callbackfnEnterThirdScene&sid=', 'json'),
    '副本挑战':         ('/modules/monster_fight.php?callback_func_name=callbackFnMonsterAction&mid=', 'json'),
    '邀请组队':         ('/modules/group.php?act=invite_group&callback_func_name=callbackFnInviteGroup&role_id=', 'json'),
    '加入队伍':         ('/modules/group.php?act=agree_invite_group&callback_func_name=callbackFnAcceptGroupInvite&group_id=', 'json'),
    '踢出队伍':         ('/modules/group.php?act=fire_out_group&callback_func_name=callbackFnFireOutGroup&role_id=', 'json'),
    
    '升级导航':         ('/modules/upgrade_help.php?act=default&callback_func_name=ajaxCallback&callback_obj_name=dlg_upgrade_help', 'soup'),

    '我的武馆':         ('/modules/team.php?act=my_team&callback_func_name=ajaxCallback&callback_obj_name=dlg_team', 'soup'),
    '武馆列表':         ('/modules/warrior.php?act=team&callback_func_name=callback_load_content%20&callback_obj_name=content', 'soup'),
    '武馆搜寻':         ('/modules/warrior.php?act=team&callback_func_name=ajaxCallback&callback_obj_name=content', 'soup'),
    '护馆':             ('/modules/team.php?act=go_into_team_scene&scene_id=1&callback_func_name=callbackFnEnterTeamScene&stand_point=0&team_id=', 'json'),
    '踢馆':             ('/modules/team.php?act=go_into_team_scene&scene_id=1&callback_func_name=callbackFnEnterTeamScene&stand_point=2&team_id=', 'json'),
    '玄武门':           ('/modules/team.php?act=team_scene_move&callback_func_name=callbackFnTeamSceneWalk&sid=2&tid=', 'soup'),
    '武馆破坏':         ('/modules/team.php?act=reduce_durable&callback_func_name=callbackFnTeamSceneReduceDurable', None),
    '武馆修复':         ('/modules/team.php?act=add_durable&callback_func_name=callbackFnTeamSceneAddDurable', None),
    '武馆经验':         ('/modules/team.php?act=view_energy&callback_func_name=ajaxCallback&callback_obj_name=view_energy_box&team_id=', 'soup'),
    '经验分配':         ('/modules/team.php?act=send_energy&submit=1&callback_func_name=ajaxCallback', 'json'),
    '奇珍园':           ('/modules/team_foster.php?act=build&action=enter&bui_id=5&callback_func_name=ajaxCallback&callback_obj_name=team_foster_build5&page=', 'soup'),
    '浇水培养':         ('/modules/team_foster.php?act=build&action=farmaction&callback_func_name=callbackTeamfarm&farm_id=', 'json'),
    '收获':             ('/modules/team_foster.php?act=build&action=farmaction&submit=1&callback_func_name=callbackTeamfarm&farm_id=', 'json'),
    '种植':             ('/modules/team_foster.php?act=build&action=farmplant&submit=0&callback_func_name=ajaxCallback&callback_obj_name=fostor_farm_plant&farm_id=', 'soup'),
    '种植提交':         ('/modules/team_foster.php?act=build&action=farmplant&submit=1', 'json'),

    '每日豪礼':         ('/modules/new_explore.php?callback_func_name=callback_load_content%20&callback_obj_name=content', 'soup'),
    '豪礼领取':         ('/modules/new_explore.php?action=enter&callback_func_name=callbackFamExplore&select_type=', 'json'),
    '每日好礼':         ('/modules/fam_explore_again.php?callback_func_name=callback_load_content%20&callback_obj_name=content', 'soup'),
    '好礼领取':         ('/modules/fam_explore_again.php?action=enter&callback_func_name=ajaxCallback&callback_obj_name=callbackFamExplore&select_type=5', None),
    '查看领取':         ('/modules/fam_explore_again.php?action=view&mirror_money_type=&select_type=5&callback_func_name=ajaxCallback&callback_obj_name=dialog0', 'soup'),

    '黄金宝石':         ('/modules/soul.php?act=gem&op=show&soul_id=385&callback_func_name=ajaxCallback&callback_obj_name=dlg_soul_gem_gem', 'wbdata'),
    '宝石抽取':         ('/modules/soul.php?act=gem&op=goldBatchPurple&soul_id=385&callback_func_name=ajaxCallback&callback_obj_name=dlg_soul_gem_gem', 'wbdata'),

    '怒海训练营':       ('/modules/sea.php?act=attack&callback_func_name=ajaxCallback&callback_obj_name=dlg_sea_attack', 'soup'),
    '训练营升级':       ('/modules/sea.php?act=upgrade&type=2&attack_id=1&callback_func_name=sea_call_back', None),
    '船坞升级':         ('/modules/sea.php?act=upgrade&type=1&item_id=1&callback_func_name=sea_call_back', None),
    '怒海争锋':         ('/modules/sea.php?act=action&callback_func_name=ajaxCallback&callback_obj_name=dlg_sea_action', 'json'),
    '海战列表':         ('/modules/sea.php?act=scene&callback_func_name=ajaxCallback&callback_obj_name=dlg_sea_action_scene&scene_id=', 'soup'),
    '海战挑战':         ('/modules/sea.php?act=fight&callback_func_name=callbackSeaFight&scene_id=', 'json'),
  
    '粉丝徽章':         ('/modules/ore.php?callback_func_name=ajaxCallback&callback_obj_name=dlg_ore&type=830', 'soup'),
    '徽章类别':         ('/modules/ore.php?callback_func_name=ajaxCallback&callback_obj_name=dlg_ore&type=', 'soup'),

    '寻访页面':         ('/modules/confidante.php?act=xun&callback_func_name=ajaxCallback&callback_obj_name=dlg_confidante_xun', 'soup'),
    '寻访':             ('/modules/confidante.php?act=enter&callback_func_name=callbackConfidanteExplore&select_type=', 'json'),

    '名将助阵':         ('/modules/famous.php?act=buf&callback_func_name=famous_call_back', 'json'),

    '组队战术':         ('/modules/group.php?act=show_fight_sequence&callback_func_name=ajaxCallback&callback_obj_name=dlg_group_sequence', 'soup'),
    '设置战术':         ('/modules/group.php?act=set_fight_sequence', 'json'),
}

beauty_cards = {
    '贡献500':         1,
    '纤纤魏女':         2,
    '楚女善饰':         3,
    '软玉温香':         4,
    '赵女娇娆':         5,
    '韩风美人':         6,
    '金枝玉叶':         9,
    '艳冶柔媚':         10,
    '婀娜娥皇':         14,
    '俏皮妹喜':         15,
    '温情骊姬':         16,
    '激活吸血':         17,
}

duel_server_command_links = {
    'home':          ('', 'soup'),
    '角色信息':       ('/modules/view_role.php?callback_func_name=ajaxCallback&callback_obj_name=dlg_view_role&role_id=', 'soup'),
    '技能信息':       ('/modules/role_skill.php?callback_func_name=callback_load_content%20&callback_obj_name=content', 'soup'),

    '领军功':         ('/modules/gacha_top.php?act=medals&submit=1&callback_func_name=callbackGetMedals', None),
    '武将探索':       ('/modules/gacha_top.php?act=normal&flag=undefined&callback_func_name=callbackGachaTop', None),
    '纵横天下':       ('/modules/war.php?callback_func_name=callback_load_content%20&callback_obj_name=content', 'soup'),
    '纵横进入战场':   ('/modules/war.php?action=enter&callback_func_name=ajaxCallback&callback_obj_name=content&sceneId=', 'soup'),
    '纵横天下刷新':   ('/modules/refresh_war_scene_data.php?action=refresh&callback_func_name=fnInitWarSceneData', 'json'),
    '纵横天下战斗':   ('/modules/war.php?action=fight&callback_func_name=callbackFnWarSceneRoleFight', None),

    '跨服奴隶':       ('/modules/slavery.php?act=view&callback_func_name=callback_load_content%20&callback_obj_name=content', 'soup'),
    '奴隶战斗':       ('/modules/slavery_fight.php?act=enemy_fight&is_reverse=1&callback_func_name=callbackFnSlaveryFight&rid=', 'json'),
    '折磨奴隶':       ('/modules/role_slavery.php?act=pain_list&type=1&action_id=0&scene_id=0&scene_type=0&callback_func_name=ajaxCallback&callback_obj_name=dlg_slave_opt_list&slave_id=', 'soup'),
    '折磨奴隶提交':   ('/modules/role_slavery.php?act=pain_submit', 'json'),
    '释放奴隶':       ('/modules/role_slavery.php?act=release_slave&callback_func_name=callbackFnReleaseSlavery&slave_id=', None),
    '逃跑':           ('/modules/slavery_top.php?act=feel&callback_func_name=callbackFnSlavery', None),

    '竞速模式':       ('/modules/trial.php?act=hall&tid=1&callback_func_name=ajaxCallback&callback_obj_name=content', 'soup'),
    '生存模式':       ('/modules/trial.php?act=hall&tid=2&callback_func_name=ajaxCallback&callback_obj_name=content', 'soup'),
    'BOSS模式':       ('/modules/trial.php?act=hall&tid=3&callback_func_name=ajaxCallback&callback_obj_name=content', 'soup'),
    '流星阁战斗':     ('/modules/trial.php?act=hall&action=fight&callback_func_name=callbackTrialRoleFight&mid=', None),
    '活跃度':         ('/modules/day_weals.php?act=weal&callback_func_name=callbackFnGetWeals&weal_id=', 'json'),

    '巅峰赛竞猜':     ('/modules/olympics.php?act=lottery&callback_func_name=ajaxCallback&callback_obj_name=dlg_olympics_lottery', 'soup'),
    '巅峰赛投票':     ('/modules/olympics.php?act=vote&callback_func_name=callbackFnLottery&role_id=', 'json'),
    '全明星竞猜':     ('/modules/star_content.php?act=lottery&callback_func_name=ajaxCallback&callback_obj_name=dlg_star_lottery', 'soup'),
    '全明星投票':     ('/modules/star_content.php?act=starlottery&callback_func_name=callbackFnStarLottery&id=', 'json'),

    '进入大副本':       ('/modules/scene_walk.php?action=world_move&callback_func_name=callbackFnWorldTransport&scene_id=', 'json'),
    '副本场景':         ('/modules/scene_walk.php?action=walk&callback_func_name=callbackfnScene&sid=', 'json'),
    '查看副本入口':     ('/modules/scene_walk.php?action=enterThirdScene&pk_status=0&hide_tips=0&isfree=0&callback_func_name=callbackfnEnterThirdScene&sid=', 'json'),
    '进入副本入口':     ('/modules/scene_walk.php?action=enterThirdScene&pk_status=0&hide_tips=1&isfree=0&callback_func_name=callbackfnEnterThirdScene&sid=', 'json'),
    '副本挑战':         ('/modules/monster_fight.php?callback_func_name=callbackFnMonsterAction&mid=', 'json'),
    '战斗查看':         ('/modules/view_combat.php?start=0&callback_func_name=ajaxCallback&callback_obj_name=dlg_view_combat&combat_id=', 'wbdata'), 
    '邀请组队':         ('/modules/group.php?act=invite_group&callback_func_name=callbackFnInviteGroup&role_id=', 'json'),
    '加入队伍':         ('/modules/group.php?act=agree_invite_group&callback_func_name=callbackFnAcceptGroupInvite&group_id=', 'json'),
    '踢出队伍':         ('/modules/group.php?act=fire_out_group&callback_func_name=callbackFnFireOutGroup&role_id=', 'json'),

    '刷新场景':       ('/modules/scene.php?callback_func_name=callback_load_stage%20&callback_obj_name=stage', 'soup'),

    '化龙榜':         ('/modules/server_duel.php?callback_func_name=callback_load_content%20&callback_obj_name=content', 'soup'),
    '化龙榜挑战':     ('/modules/server_duel_fight.php?action=fight&callback_func_name=callbackFnServerDuelRoleFight&rank=', 'json'),

    '威望换勋章':     ('/modules/slavery_shop.php?op=buy&itemID=4&callback_func_name=callbackfnBusPveReward', 'json'),
}

class AuxSkillError(Exception):
    def __init__(self, message: str='装备辅助技能错误') -> None:
        super().__init__(message)
        self.message = message

class Command:
    def __init__(self, role: str, base_url: str, headers: dict, user_logger) -> None:
        self.role = role
        self.base_url = base_url
        self.headers = headers
        self.user_logger = user_logger
        self.duel_cookies = None  # Store cookies for duel.50hero.com

    def __call__(self, command: str|None=None, link: str='', id: str='', is_duel_command: bool=False, return_type: str='wbdata') -> Any:

        if link.startswith('http://') or link.startswith('https://'):
            url = f'{link}{id}'
            is_duel_command = 'duel.50hero.com' in url
        elif not command:
            # When command is None and link is provided, check if it should be a duel command
            if is_duel_command:
                url = f'http://duel.50hero.com{link}{id}'
            else:
                url = f'{self.base_url}{link}{id}'
        else:
            if is_duel_command:
                link, return_type = duel_server_command_links.get(command, (link, None))
                url = f'http://duel.50hero.com{link}{id}'
            else:
                link, return_type = command_links.get(command, (link, None))
                url = f'{self.base_url}{link}{id}'

            if not link and command != 'home':
                raise Exception(f'{self.role}: 没有找到命令 {command} 的链接')

        request_headers = self.headers.copy()
        if is_duel_command:
            if self.duel_cookies is None:
                self.user_logger.info(f'{self.role}: 首次访问跨服，正在进入...')
                self.enter_duel_server()
            else:
                self.user_logger.debug(f'{self.role}: 使用已缓存的跨服会话')
            self.user_logger.debug(f'{self.role}: 跨服请求 URL: {url}')
            request_headers['Cookie'] = self.duel_cookies

        # Use retry helper for connection errors
        def make_request():
            return requests.get(url, headers=request_headers, timeout=DEFAULT_REQUEST_TIMEOUT)

        ret = retry_on_connection_error(make_request, self.role)

        # If this is a duel domain request, capture/merge cookies only if we don't have them yet
        if is_duel_command and ret.cookies and not self.duel_cookies:
            # Build cookie string from response
            cookie_parts = []
            for key, value in ret.cookies.items():
                cookie_parts.append(f'{key}={value}')
            if cookie_parts:
                self.duel_cookies = '; '.join(cookie_parts)
                if self.user_logger:
                    self.user_logger.info(f'{self.role}: 已捕获 duel.50hero.com 的 cookies')
        
        try:
            wbdata = ret.text
        except (urllib3.exceptions.ProtocolError, requests.exceptions.ChunkedEncodingError) as e:
            # Handle incomplete reads / broken connections during response reading
            if self.user_logger:
                self.user_logger.warning(f'{self.role}: 数据传输不完整，尝试重新请求: {e}')
            time.sleep(2)
            return self(command, link, id, is_duel_command, return_type)
        except Exception as e:
            if 'gzip' in str(e).lower() or 'decompress' in str(e).lower():
                if self.user_logger:
                    self.user_logger.warning(f'{self.role}: Gzip解压错误，尝试重新请求: {e}')
                time.sleep(2)
                return self(command, link, id, is_duel_command, return_type)
            else:
                return None
        
        time.sleep(1)
        try:
            # when the request call returns a json object instead of html page, something wrong
            # Strip BOM (Byte Order Mark) and whitespace that can cause json.loads to fail
            wbdata_clean = wbdata.lstrip('\ufeff').strip()
            data = json.loads(wbdata_clean)

            # somehow this is a special case, the error is not True, but the result is a string
            if '你口中念念有词' in data.get('result', ''): data['error'] = False
            if data.get('error', False):
                message = data.get('result', '')
                if '操作过于频繁，还请稍后再试' in message or '在战斗结束 5' in message:
                    self.user_logger.info(f'{self.role}: 操作过于频繁, 3秒后重试')
                    time.sleep(3)
                    return self(command, link, id)
                return data
            return data if return_type == 'json' else wbdata
        except json.decoder.JSONDecodeError:
            if return_type == 'wbdata': return wbdata
            return BeautifulSoup(wbdata, 'lxml')
        except Exception as e:
            if return_type == 'wbdata': return wbdata
            return BeautifulSoup(wbdata, 'lxml')

    def activate_beauty_card(self, card: str) -> int:
        self.user_logger.info(f'{self.role}: 激活美女图: {card}')
        ret = self.__call__('美女图', id=beauty_cards[card])
        return ret

    def get_role_info(self) -> dict:
        wbdata = self.__call__('角色信息')
        soup = BeautifulSoup(wbdata, 'lxml')

        ret = {}
        all_td_elements = soup.find_all('td')
        for element in all_td_elements:
            if '职业：' in element.text:
                span_element = element.find_next('span', class_='highlight')
                ret['职业'] = span_element.text.strip()
                
        elements = soup.find_all('div', class_='point_bar_bg')
        for element in elements:
            title_element = element['title']
            title_soup = BeautifulSoup(title_element, 'html.parser')
            contents = title_soup.find_all('span')
            if '臂力' in title_element:
                ret['臂力'] = int(contents[0].text.strip()) + int(contents[1].text.strip('+'))
            elif '身法' in title_element:
                ret['身法'] = int(contents[0].text.strip()) + int(contents[1].text.strip('+'))
            elif '根骨' in title_element:
                ret['根骨'] = int(contents[0].text.strip()) + int(contents[1].text.strip('+'))

        return ret

    def get_role_attr(self) -> dict:
        soup = self.__call__('角色属性')

        elements = soup.find_all('td', style="width: 300px;height:320px;border:1px solid #C9C0AE;padding-left:5px;line-height:24px;")
        text = elements[0].get_text(strip=True) + elements[1].get_text(strip=True)

        cleaned_text = re.sub(r'[+()% ]', '', text)

        pattern = re.compile(r'([^：]+)：([\d\-,.]+)')

        # Use findall to get all matches in the text
        result_dict = {}
        matches = pattern.findall(cleaned_text)
        for m in matches:
            key, value = m
            if '-' in value:
                value = value.split('-')[1]
            value = value.replace(',', '').strip()
            if value.isdigit(): value = int(value)
            if key == '快伤害减免': key = '伤害减免'
            result_dict[key] = value

        return result_dict

    def post(self, command: str='', data: dict=None, is_duel_command: bool=False, id: str='') -> Any:
        """POST request method for form submissions"""
        if is_duel_command:
            link, type = duel_server_command_links.get(command, ('', None))
            url = f'http://duel.50hero.com{link}{id}'
        else:
            link, type = command_links.get(command, ('', None))
            url = f'{self.base_url}{link}{id}'

        request_headers = self.headers.copy()
        if is_duel_command:
            if self.duel_cookies is None:
                self.user_logger.info(f'{self.role}: 首次访问跨服，正在进入...')
                self.enter_duel_server()
            else:
                self.user_logger.debug(f'{self.role}: 使用已缓存的跨服会话')
            self.user_logger.debug(f'{self.role}: 跨服POST请求 URL: {url}')
            request_headers['Cookie'] = self.duel_cookies

        # Use retry helper for connection errors
        def make_request():
            return requests.post(url, headers=request_headers, data=data, timeout=DEFAULT_REQUEST_TIMEOUT)

        ret = retry_on_connection_error(make_request, self.role)
        
        try:
            wbdata = ret.text
        except (urllib3.exceptions.ProtocolError, requests.exceptions.ChunkedEncodingError) as e:
            # Handle incomplete reads / broken connections during response reading
            self.user_logger.warning(f'{self.role}: 数据传输不完整，尝试重新请求: {e}')
            time.sleep(2)
            return self.post(command, data, is_duel_command, id)
        except Exception as e:
            if 'gzip' in str(e).lower() or 'decompress' in str(e).lower():
                self.user_logger.warning(f'{self.role}: Gzip解压错误，尝试重新请求: {e}')
                time.sleep(2)
                return self.post(command, data, is_duel_command, id)
            else:
                return None
        
        time.sleep(1)
        try:
            # when the request call returns a json object instead of html page, something wrong
            temp_data = json.loads(wbdata)
            if temp_data.get('error', False):
                message = temp_data.get('result', '')
                if '操作过于频繁，还请稍后再试' in message:
                    self.user_logger.info(f'{self.role}: 操作过于频繁, 3秒后重试')
                    time.sleep(3)
                    return self.post(command, data, id=id)
                if type == 'wbdata' or type == 'soup':
                    return None

            return temp_data if type == 'json' else wbdata
        except json.decoder.JSONDecodeError:
            if type == 'wbdata': return wbdata
            if type == 'soup': return BeautifulSoup(wbdata, 'lxml')
        except Exception as e:
            self.user_logger.error(f'{self.role}: 处理响应时出错: {e}')
            return None

    def enter_duel_server(self) -> str:
        """
        Enter the duel server to establish session and get cookies.
        Returns the duel server URL base.
        """
        try:
            # Step 1: Get the enter URL from main server
            enter_link = '/api/duel/enter.php?rand=1'
            url = f'{self.base_url}{enter_link}'
            
            # self.user_logger.info(f'{self.role}: 正在获取跨服竞技场入口...')
            
            ret = retry_on_connection_error(lambda: requests.get(url, headers=self.headers, timeout=DEFAULT_REQUEST_TIMEOUT), self.role)
            
            # The response contains a JavaScript redirect
            # Example: <script type="text/javascript">window.location.href='URL'</script>
            try:
                # First try parsing as JSON
                data = json.loads(ret.text)
                if 'url' in data:
                    duel_enter_url = data['url']
                else:
                    raise Exception("响应中未找到 URL")
            except json.decoder.JSONDecodeError:
                # Extract URL from JavaScript redirect
                match = re.search(r"window\.location\.href\s*=\s*['\"]([^'\"]+)['\"]", ret.text)
                if match:
                    duel_enter_url = match.group(1)
                else:
                    # Fallback: if it's a plain URL
                    duel_enter_url = ret.text.strip()
            
            if not duel_enter_url.startswith('http'):
                raise Exception(f"无效的跨服 URL: {duel_enter_url}")
            
            # self.user_logger.info(f'{self.role}: 正在访问跨服竞技场以建立会话...')
            
            # Step 2: Visit the enter URL to establish session and get cookies
            # Use a session object to automatically handle cookies
            session = requests.Session()
            session.headers.update(self.headers)
            enter_response = retry_on_connection_error(lambda: session.get(duel_enter_url, timeout=DEFAULT_REQUEST_TIMEOUT, allow_redirects=True), self.role)
            
            # Step 3: Extract cookies from the session
            cookie_parts = []
            for cookie in session.cookies:
                cookie_parts.append(f'{cookie.name}={cookie.value}')
            
            if cookie_parts:
                self.duel_cookies = '; '.join(cookie_parts)
                self.user_logger.info(f'{self.role}: 已成功进入跨服竞技场并获取会话 (cookies: {len(cookie_parts)} 个)')
                self.user_logger.debug(f'{self.role}: 跨服 cookies: {self.duel_cookies}')
            else:
                self.user_logger.warning(f'{self.role}: 未获取到跨服 cookies，可能需要检查响应')
            
            # Return the base duel URL
            return 'http://duel.50hero.com'
            
        except Exception as e:
            self.user_logger.error(f'{self.role}: 进入跨服竞技场失败: {e}')
            raise

    def exchange_reward(self, id: str, num: int=1) -> Any:
        link, _ = command_links.get('兑换奖励')
        url = f'{self.base_url}{link}{id}'
        url = url.replace('num=1', f'num={num}')
        return self.__call__(link=url, return_type='json')

    def get_scene_data(self, key: str|None=None, scene_type: str='callbackfnScene', is_duel_command: bool=False) -> Any:
        scene_response = self.__call__('刷新场景', is_duel_command=is_duel_command)
        
        # Extract JSON from callbackfnScene( {...} , true );
        callback_match = re.search(rf'{re.escape(scene_type)}\s*\(\s*({{.*?}})\s*,\s*true\s*\)', str(scene_response), re.DOTALL)
        if callback_match:
            scene_json_str = callback_match.group(1)
            scene_data = json.loads(scene_json_str)
            return scene_data.get(key) if key else scene_data

