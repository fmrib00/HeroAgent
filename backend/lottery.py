from character import Character
import re

def character_lottery(character: Character, lottery_type: str):
    if lottery_type == '巅峰赛':
        command = '巅峰赛竞猜'
    elif lottery_type == '全明星':
        command = '全明星竞猜'
    else:
        character.user_logger.error(f'{character.name}: 未设置竞猜类型')
        return []
    soup = character.command(command, is_duel_command=True)
    
    # Find the table containing the lottery data
    table = soup.find('table', class_='data_grid')
    if not table:
        return []
    
    if lottery_type == '巅峰赛':
        return _parse_peak_tournament_lottery(table)
    elif lottery_type == '全明星':
        return _parse_all_star_lottery(table)
    
    return []

def _parse_peak_tournament_lottery(table):
    """Parse 巅峰赛 lottery HTML structure"""
    # Extract characters grouped by 竞猜组别
    groups = []
    current_group = None
    current_group_name = None
    
    # Iterate through all rows in the table
    for tr in table.find_all('tr'):
        # Check if this is a group header row (contains "竞猜组别")
        # Look for td that contains text with "竞猜组别"
        group_header = None
        for td in tr.find_all('td'):
            td_text = td.get_text(strip=True)
            if '竞猜组别' in td_text:
                group_header = td
                break
        
        if group_header:
            # Save previous group if it exists
            if current_group is not None:
                groups.append({
                    'group_name': current_group_name,
                    'characters': current_group
                })
            
            # Start a new group
            # Extract group name from <span class="highlight">130级组</span>
            global_index = 1
            highlight_span = group_header.find('span', class_='highlight')
            if highlight_span:
                current_group_name = highlight_span.get_text(strip=True)
                current_group = []
        
        # Check if this row contains character links
        elif current_group is not None:
            # Find all <img> tags with onclick containing olympic_lottery in this row
            # The onclick format is: onclick="olympic_lottery(role_id, group_id)"
            for img in tr.find_all('img', onclick=re.compile(r'olympic_lottery')):
                onclick = img.get('onclick', '')
                # Extract role_id and group_id from onclick="olympic_lottery(14871, 1)"
                match = re.search(r'olympic_lottery\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)', onclick)
                if match:
                    view_role_id = match.group(1)
                    group_id = match.group(2)
                    
                    # Find the corresponding <a> tag in the same row to get character name
                    # The <a> tag with the same role_id should be in the same row
                    # Look for <a> tag with onclick="view_role ( role_id )"
                    link = None
                    for a_tag in tr.find_all('a', onclick=re.compile(r'view_role')):
                        a_onclick = a_tag.get('onclick', '')
                        a_match = re.search(r'view_role\s*\(\s*(\d+)\s*\)', a_onclick)
                        if a_match and a_match.group(1) == view_role_id:
                            link = a_tag
                            break
                    
                    # If not found by matching role_id, just get the first one in the row
                    if link is None:
                        link = tr.find('a', onclick=re.compile(r'view_role'))
                    
                    character_name = link.get_text(strip=True) if link else f'角色{view_role_id}'
                    
                    current_group.append({
                        'index': global_index,
                        'name': character_name,
                        'view_role_id': view_role_id,
                        'group_id': group_id
                    })
                    global_index += 1
    
    # Don't forget to add the last group
    if current_group is not None:
        groups.append({
            'group_name': current_group_name,
            'characters': current_group
        })

    return groups

def _parse_all_star_lottery(table):
    """Parse 全明星 lottery HTML structure"""
    groups = []
    match_index = 1
    
    # Iterate through all rows in the table (skip header row)
    for tr in table.find_all('tr')[1:]:  # Skip first row which is header
        # Check if this row contains star_lottery onclick handlers
        # Each row represents a match with two teams
        imgs = tr.find_all('img', onclick=re.compile(r'star_lottery'))
        if not imgs:
            continue
        
        # Extract both teams from this match
        # Structure: <td><a>Team1</a></td><td><img onclick="star_lottery(match_id, team_id1)"></td>
        #            <td>VS</td>
        #            <td><a>Team2</a></td><td><img onclick="star_lottery(match_id, team_id2)"></td>
        match_teams = []
        team_index = 1
        
        # Get all <td> elements in this row
        tds = tr.find_all('td')
        
        for img in imgs:
            onclick = img.get('onclick', '')
            # Extract match_id and team_id from onclick="star_lottery(380, 1)"
            match = re.search(r'star_lottery\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)', onclick)
            if match:
                match_id = match.group(1)
                team_id = match.group(2)
                
                # Find the corresponding <a> tag for this team
                # The <a> tag is in the <td> immediately before the <td> containing this <img>
                link = None
                img_td = img.find_parent('td')
                if img_td and img_td in tds:
                    img_td_index = tds.index(img_td)
                    # The <a> tag should be in the previous <td>
                    if img_td_index > 0:
                        prev_td = tds[img_td_index - 1]
                        link = prev_td.find('a')
                
                # If not found, try to find any unused <a> tag in the row
                if link is None:
                    used_names = [t['name'] for t in match_teams]
                    for a_tag in tr.find_all('a'):
                        team_name = a_tag.get_text(strip=True)
                        if team_name and team_name not in used_names:
                            link = a_tag
                            break
                
                team_name = link.get_text(strip=True) if link else f'队伍{team_id}'
                
                match_teams.append({
                    'index': team_index,
                    'name': team_name,
                    'match_id': match_id,
                    'team_id': team_id
                })
                team_index += 1
        
        # Add this match as a group
        if match_teams:
            groups.append({
                'group_name': f'第{match_index}场',
                'characters': match_teams  # Reusing 'characters' key for consistency
            })
            match_index += 1
    
    return groups

def submit_lottery_votes(character: Character, lottery_type: str, lottery_numbers: str):
    """Submit lottery votes based on lottery_numbers string"""
    if lottery_type == '巅峰赛':
        command_prefix = '巅峰赛投票'
    elif lottery_type == '全明星':
        command_prefix = '全明星投票'
    else:
        character.user_logger.error(f'{character.name}: 未设置竞猜类型')
        return
    
    # First, get the groups to know how many groups there are
    groups = character_lottery(character, lottery_type)
    if not groups:
        character.user_logger.error(f'{character.name}: 无法获取竞猜组别信息')
        return
    
    # Validate lottery_numbers length matches number of groups
    if len(lottery_numbers) != len(groups):
        character.user_logger.error(f'{character.name}: 竞猜号码长度 ({len(lottery_numbers)}) 与组别数量 ({len(groups)}) 不匹配')
        return
    
    # Submit vote for each group
    for group_index, (group_number_char, group) in enumerate(zip(lottery_numbers, groups), start=1):
        group_number = int(group_number_char)
        
        # Validate group_number is within range
        if group_number < 1 or group_number > len(group['characters']):
            character.user_logger.error(f'{character.name}: 组别 {group_index} 的号码 {group_number} 超出范围 (1-{len(group["characters"])})')
            continue
        
        # Get the selected character/team information
        selected_item = group['characters'][group_number - 1]  # -1 because index starts from 0
        
        if lottery_type == '巅峰赛':
            # For 巅峰赛: use view_role_id and group_id
            role_id = selected_item['view_role_id']
            group_id = selected_item['group_id']
            # Submit vote: command is '巅峰赛投票' with id=f'{role_id}&group_id={group_id}'
            # The URL becomes: /modules/olympics.php?act=vote&callback_func_name=callbackFnLottery&role_id={role_id}&group_id={group_id}
            vote_id = f'{role_id}&group_id={group_id}'
            character.user_logger.info(f'{character.name}: 组别 {group_id} ({group["group_name"]}) 投票给 [{group_number}] {selected_item["name"]} (role_id: {role_id})')
        elif lottery_type == '全明星':
            # For 全明星: use match_id and team_id
            match_id = selected_item['match_id']
            team_id = selected_item['team_id']
            # Submit vote: command is '全明星投票' with id=f'{match_id}&team_id={team_id}'
            # The URL becomes: /modules/star_content.php?act=starlottery&callback_func_name=callbackFnStarLottery&id={match_id}&team_id={team_id}
            vote_id = f'{match_id}&team_id={team_id}'
            character.user_logger.info(f'{character.name}: {group["group_name"]} 投票给 [{group_number}] {selected_item["name"]} (match_id: {match_id}, team_id: {team_id})')
        
        character.command(command_prefix, id=vote_id, is_duel_command=True)
    
    return True
