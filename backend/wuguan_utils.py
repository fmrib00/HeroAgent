"""
Utility functions for extracting information from wuguan (武馆) pages
"""
import re
from bs4 import BeautifulSoup
from log import logger
from typing import Optional
from command import Command

def extract_player_position(soup: BeautifulSoup) -> str:
    """
    Extract player's position (立场) from wuguan page.
    
    This extracts the text "你的立场是【护馆方】", "你的立场是【踢馆方】", or "你的立场是【闲逛方】"
    from the wuguan scene page.
    
    Args:
        soup: BeautifulSoup object of the wuguan page
    
    Returns:
        str: Position value ('护馆方', '踢馆方', or '闲逛方'). Returns 'unknown' if not found.
    """
    try:
        # Get all text content from the page
        page_text = soup.get_text() if soup else ""
        
        # Pattern to match: 你的立场是【XXX】
        # Using [^】] instead of \w to properly match Chinese characters
        pattern = r'你的立场是【([^】]+)】'
        match = re.search(pattern, page_text)
        
        if match:
            position = match.group(1)
            logger.debug(f"Extracted position: {position}")
            return position
        else:
            logger.warning("Could not find player position on page")
            return "unknown"
            
    except Exception as e:
        logger.error(f"Error extracting player position: {e}")
        return "unknown"


def extract_stay_time(soup: BeautifulSoup) -> int:
    """
    Extract the stay time (停留时间) in minutes from wuguan page.
    
    Args:
        soup: BeautifulSoup object of the wuguan page
    
    Returns:
        int: Stay time in minutes. Returns -1 if not found.
    """
    try:
        page_text = soup.get_text() if soup else ""
        
        # Pattern to match: 停留时间：XXX分钟
        pattern = r'停留时间：(\d+)分钟'
        match = re.search(pattern, page_text)
        
        if match:
            stay_time = int(match.group(1))
            logger.debug(f"Extracted stay time: {stay_time} minutes")
            return stay_time
        else:
            logger.warning("Could not find stay time on page")
            return -1
            
    except Exception as e:
        logger.error(f"Error extracting stay time: {e}")
        return -1


def extract_brick_count(soup: BeautifulSoup) -> tuple[int, int]:
    """
    Extract brick counts from wuguan page.
    
    Args:
        soup: BeautifulSoup object of the wuguan page
    
    Returns:
        tuple: (current_bricks, required_bricks). Returns (-1, -1) if not found.
    """
    try:
        page_text = soup.get_text() if soup else ""
        
        # Extract current brick count: 当前已经积累 XXX 块板砖
        current_pattern = r'当前已经积累\s+([\d,]+)\s+块板砖'
        current_match = re.search(current_pattern, page_text)
        
        current_bricks = -1
        if current_match:
            current_str = current_match.group(1).replace(',', '')
            current_bricks = int(current_str)
            logger.debug(f"Extracted current bricks: {current_bricks}")
        
        # Extract required brick count: 必须至少积累 XXX 块板砖
        required_pattern = r'必须至少积累\s+([\d,]+)\s+块板砖'
        required_match = re.search(required_pattern, page_text)
        
        required_bricks = -1
        if required_match:
            required_str = required_match.group(1).replace(',', '')
            required_bricks = int(required_str)
            logger.debug(f"Extracted required bricks: {required_bricks}")
        
        return (current_bricks, required_bricks)
        
    except Exception as e:
        logger.error(f"Error extracting brick counts: {e}")
        return (-1, -1)


def extract_durability_info(soup: BeautifulSoup) -> tuple[int, int]:
    """
    Extract current and max durability from wuguan scene.
    
    Args:
        soup: BeautifulSoup object of the wuguan page
    
    Returns:
        tuple: (current_durability, max_durability). Returns (-1, -1) if not found.
    """
    try:
        page_text = soup.get_text() if soup else ""
        
        # Pattern to match: 当前驻点耐久：1,152,100 / 1,152,100
        pattern = r'当前驻点耐久：([\d,]+)\s*/\s*([\d,]+)'
        match = re.search(pattern, page_text)
        
        if match:
            current_str = match.group(1).replace(',', '')
            max_str = match.group(2).replace(',', '')
            current_durability = int(current_str)
            max_durability = int(max_str)
            logger.debug(f"Extracted durability: {current_durability} / {max_durability}")
            return (current_durability, max_durability)
        else:
            logger.warning("Could not find durability info on page")
            return (-1, -1)
            
    except Exception as e:
        logger.error(f"Error extracting durability info: {e}")
        return (-1, -1)


def extract_open_hours(soup: BeautifulSoup) -> str:
    """
    Extract wuguan open hours from page.
    
    Args:
        soup: BeautifulSoup object of the wuguan page
    
    Returns:
        str: Open hours (e.g., "8:00 - 16:00"). Returns empty string if not found.
    """
    try:
        page_text = soup.get_text() if soup else ""
        
        # Pattern to match: 本武馆开放时间：8:00 - 16:00
        pattern = r'本武馆开放时间：([\d:]+\s*-\s*[\d:]+)'
        match = re.search(pattern, page_text)
        
        if match:
            hours = match.group(1).strip()
            logger.debug(f"Extracted open hours: {hours}")
            return hours
        else:
            logger.warning("Could not find open hours on page")
            return ""
            
    except Exception as e:
        logger.error(f"Error extracting open hours: {e}")
        return ""


def get_wuguan_info(soup: BeautifulSoup) -> dict:
    """
    Extract comprehensive wuguan information from page.
    
    Args:
        soup: BeautifulSoup object of the wuguan page
    
    Returns:
        dict: Dictionary containing all extracted wuguan information
    """
    info = {
        'position': extract_player_position(soup),
        'stay_time_minutes': extract_stay_time(soup),
        'bricks': {
            'current': extract_brick_count(soup)[0],
            'required': extract_brick_count(soup)[1]
        },
        'durability': {
            'current': extract_durability_info(soup)[0],
            'max': extract_durability_info(soup)[1]
        },
        'open_hours': extract_open_hours(soup)
    }
    
    logger.info(f"Extracted wuguan info: position={info['position']}, "
                f"stay_time={info['stay_time_minutes']}min, "
                f"bricks={info['bricks']['current']}/{info['bricks']['required']}")
    
    return info


def soup_from_wuguan_list_response(response_text: str) -> BeautifulSoup:
    """
    Build a BeautifulSoup from the 武馆列表接口返回文本.

    The endpoint `/modules/warrior.php?act=team&callback_func_name=callback_load_content&callback_obj_name=content`
    may return content wrapped in a callback like: callback_load_content('<div>...html...</div>');

    This function extracts the HTML payload, unescapes it, and returns a Soup.

    Args:
        response_text: Raw text returned by the endpoint

    Returns:
        BeautifulSoup: Parsed soup of the inner HTML. If extraction fails, falls back to parsing the raw text.
    """
    try:
        if not response_text:
            return BeautifulSoup('', 'html.parser')

        text = response_text.strip()
        # Try to match callback_load_content('...') style wrapper
        m = re.search(r"callback_load_content\s*\(\s*([\"'])([\s\S]*?)\1\s*\)\s*;?\s*$", text)
        if m:
            payload = m.group(2)
            # Unescape common JS string escapes
            payload = payload.replace(r"\n", "\n").replace(r"\t", "\t")
            payload = payload.replace(r"\"", '"').replace(r"\'", "'")
            # Some backslashes may remain that escape nothing; keep them as is
            return BeautifulSoup(payload, 'html.parser')

        # Sometimes the server may return raw HTML fragment
        return BeautifulSoup(text, 'html.parser')
    except Exception as e:
        logger.error(f"Error building soup from wuguan list response: {e}")
        # Best-effort fallback
        return BeautifulSoup(response_text or '', 'html.parser')


def extract_wuguan_id_by_name(soup: BeautifulSoup, target_name: str) -> int:
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
