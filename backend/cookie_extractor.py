"""
Cookie extraction utility using Playwright for automated login and cookie extraction.
This module provides functionality to automate the game login process and extract
the required cookies (weeCookie and 50hero_session).
"""
import asyncio
import time
import threading
from typing import Optional, Dict
from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError
from log import logger

# Store browser contexts to keep them alive
_active_browser_contexts = {}
_context_lock = threading.Lock()

# Game URL
GAME_URL = "https://hero.9wee.com"

async def extract_cookies(username: str, password: str, game_url: Optional[str] = None, timeout: int = 60) -> Dict[str, Optional[str]]:
    """
    Automatically log in to the game and extract cookies.
    
    Args:
        username: Game account username
        password: Game account password
        game_url: Game URL to navigate to (defaults to GAME_URL if not provided)
        timeout: Maximum time to wait for login completion (seconds)
    
    Returns:
        Dictionary containing:
        - 'cookie_string': Formatted cookie string ready to use (svr=...;weeCookie=...)
        - 'weeCookie': Raw weeCookie value
        - '50hero_session': Raw 50hero_session value
        - 'success': Boolean indicating success
        - 'error': Error message if failed
    
    Raises:
        Exception: If login fails or cookies cannot be extracted
    """
    # Use provided URL or default
    target_url = game_url or GAME_URL
    browser: Optional[Browser] = None
    try:
        async with async_playwright() as p:
            # Launch browser in headless mode with Linux-compatible arguments
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--disable-gpu',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-blink-features=AutomationControlled',  # Hide automation indicators
                    '--disable-features=site-per-process',  # Allow cross-site navigation
                    '--ignore-certificate-errors',  # Ignore SSL certificate errors
                    '--allow-running-insecure-content'  # Allow mixed content
                ]
            )
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                ignore_https_errors=True,
                # Allow redirects and handle them properly
                java_script_enabled=True,
                # Set a reasonable viewport
                viewport={'width': 1920, 'height': 1080},
                # Add extra headers to appear more like a real browser
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
            )
            page = await context.new_page()
            
            # Set up better error handling for navigation
            page.on("requestfailed", lambda request: logger.warning(f"Request failed: {request.url} - {request.failure}"))
            
            logger.info(f"Navigating to game URL: {target_url}")
            # Try multiple strategies: start with the most lenient, then try stricter ones
            navigation_success = False
            last_error = None
            
            # Strategy 1: Try with domcontentloaded (most lenient, doesn't wait for all resources)
            try:
                logger.info("Attempting navigation with domcontentloaded...")
                response = await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
                if response:
                    logger.info(f"Page loaded with domcontentloaded. Status: {response.status}, Final URL: {page.url}")
                else:
                    logger.info(f"Page navigation completed (no response object). Final URL: {page.url}")
                navigation_success = True
            except Exception as e1:
                last_error = e1
                error_msg = str(e1)
                logger.warning(f"domcontentloaded failed: {error_msg}")
                
                # Strategy 2: Try with commit (even more lenient - just waits for navigation to commit)
                if "ERR_CONNECTION_REFUSED" not in error_msg:
                    try:
                        logger.info("Attempting navigation with commit...")
                        response = await page.goto(target_url, wait_until="commit", timeout=60000)
                        if response:
                            logger.info(f"Page loaded with commit. Status: {response.status}, Final URL: {page.url}")
                        else:
                            logger.info(f"Page navigation committed. Final URL: {page.url}")
                        # Wait a bit for page to settle
                        await page.wait_for_timeout(3000)
                        navigation_success = True
                    except Exception as e2:
                        last_error = e2
                        logger.warning(f"commit also failed: {str(e2)}")
                
                # Strategy 3: Try navigating to the base domain first, then let it redirect
                if not navigation_success and "ERR_CONNECTION_REFUSED" in error_msg:
                    # If connection refused to s2.hero.9wee.com, try the main domain first
                    if "s2.hero.9wee.com" in target_url or "s" in target_url.split(".")[0]:
                        base_url = target_url.replace("s2.", "").replace("s1.", "").replace("s3.", "").replace("s4.", "").replace("s5.", "")
                        if base_url != target_url:
                            logger.info(f"Connection refused to {target_url}, trying base URL: {base_url}")
                            try:
                                response = await page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
                                await page.wait_for_timeout(3000)
                                logger.info(f"Base URL navigation successful. Final URL: {page.url}")
                                navigation_success = True
                            except Exception as e_base:
                                logger.warning(f"Base URL navigation also failed: {str(e_base)}")
                
                # Strategy 4: Try without wait_until (just navigate and wait manually)
                if not navigation_success and "ERR_CONNECTION_REFUSED" not in error_msg:
                    try:
                        logger.info("Attempting navigation without wait_until...")
                        response = await page.goto(target_url, timeout=60000)
                        # Wait manually for page to load
                        await page.wait_for_timeout(5000)
                        logger.info(f"Navigation completed. Final URL: {page.url}")
                        navigation_success = True
                    except Exception as e3:
                        last_error = e3
                        logger.warning(f"Navigation without wait_until failed: {str(e3)}")
            
            if not navigation_success:
                # Log the actual URL that failed
                current_url = page.url if page.url else "unknown"
                error_msg = str(last_error) if last_error else "Unknown error"
                logger.error(f"All navigation strategies failed. Attempted URL: {target_url}, current URL: {current_url}, error: {error_msg}")
                
                # Check if we're on an error page (Chrome error pages indicate failure)
                # Check for various Chrome error page patterns - must check this FIRST
                is_error_page = (
                    current_url.startswith("chrome-error://") or 
                    current_url.startswith("chrome://") or 
                    current_url.startswith("about:error") or
                    "chromewebdata" in current_url.lower()
                )
                
                if is_error_page:
                    if "ERR_CONNECTION_REFUSED" in error_msg or "ERR_CONNECTION_REFUSED" in current_url or "connection_refused" in current_url.lower():
                        raise Exception(f"Connection refused to {target_url}. The server is not reachable from this machine. This may be due to:\n"
                                       f"1. Network/firewall restrictions blocking access to the server\n"
                                       f"2. The server being down or unreachable\n"
                                       f"3. DNS resolution issues\n"
                                       f"Please verify the URL is accessible (try: curl {target_url} or ping the domain)")
                    raise Exception(f"Failed to navigate to game URL: {target_url}. Browser error page detected: {current_url}. Error: {error_msg}")
                # Check if we're on a different URL (might have redirected successfully)
                # Only treat as success if it's NOT an error page and is a valid HTTP/HTTPS URL
                elif (current_url != "about:blank" and 
                      current_url != target_url and 
                      (current_url.startswith("http://") or current_url.startswith("https://"))):
                    logger.info(f"Page appears to have navigated to different URL: {current_url}, continuing...")
                    navigation_success = True
                else:
                    # Provide more helpful error message
                    if "ERR_CONNECTION_REFUSED" in error_msg or "net::ERR" in error_msg:
                        raise Exception(f"Connection refused to {target_url}. The URL may be redirecting to a server that's not accessible. Current URL: {current_url}. Please verify the URL is correct and accessible from this server.")
                    raise Exception(f"Failed to navigate to game URL: {target_url}. Error: {error_msg}")
            
            # Log final URL after navigation and verify it's not an error page
            final_url = page.url
            
            # Check if we're on an error page (Chrome error pages indicate connection failure)
            # This is a safety check in case navigation_success was incorrectly set to True
            is_error_page_final = (
                final_url.startswith("chrome-error://") or 
                final_url.startswith("chrome://") or 
                final_url.startswith("about:error") or
                "chromewebdata" in final_url.lower()
            )
            
            if is_error_page_final:
                error_text = ""
                try:
                    # Try to get error message from the page
                    error_element = await page.query_selector("body")
                    if error_element:
                        error_text = await error_element.inner_text()
                except:
                    pass
                
                if "ERR_CONNECTION_REFUSED" in str(last_error) or "ERR_CONNECTION_REFUSED" in error_text:
                    raise Exception(f"Connection refused to {target_url}. The server is not reachable from this machine. This may be due to:\n"
                                   f"1. Network/firewall restrictions blocking access to the server\n"
                                   f"2. The server being down or unreachable\n"
                                   f"3. DNS resolution issues\n"
                                   f"Please verify the URL is accessible (try: curl {target_url} or ping the domain)")
                else:
                    raise Exception(f"Navigation resulted in browser error page: {final_url}. The URL {target_url} may be unreachable or blocked. Error details: {error_text if error_text else 'Unknown error'}")
            
            logger.info(f"Navigation successful. Final URL: {final_url}")
            
            # Wait a bit for page to fully load
            await page.wait_for_timeout(2000)
            
            # Try to find login form elements
            # Common selectors for login forms (try multiple variations)
            login_selectors = [
                # Standard form inputs
                ('input[name="username"]', 'input[name="password"]', 'button[type="submit"], input[type="submit"], button:has-text("登录"), button:has-text("登陆")'),
                ('input[id="username"]', 'input[id="password"]', 'button[type="submit"], input[type="submit"]'),
                ('input[type="text"]', 'input[type="password"]', 'button[type="submit"], input[type="submit"]'),
                ('#username', '#password', 'button[type="submit"], input[type="submit"]'),
                # Chinese form labels
                ('input[placeholder*="用户名"], input[placeholder*="账号"], input[placeholder*="账户"]', 
                 'input[type="password"]', 
                 'button[type="submit"], input[type="submit"], button:has-text("登录"), button:has-text("登陆")'),
                # Generic text input + password
                ('input[type="text"]:not([type="hidden"])', 'input[type="password"]', 
                 'button[type="submit"], input[type="submit"], form button, form input[type="submit"]'),
            ]
            
            username_input = None
            password_input = None
            submit_button = None
            
            # Try to find login form
            for user_sel, pass_sel, submit_sel in login_selectors:
                try:
                    # Try to find username input
                    username_elements = await page.query_selector_all(user_sel)
                    password_elements = await page.query_selector_all(pass_sel)
                    submit_elements = await page.query_selector_all(submit_sel)
                    
                    if username_elements and password_elements and submit_elements:
                        username_input = username_elements[0]
                        password_input = password_elements[0]
                        submit_button = submit_elements[0]
                        logger.info(f"Found login form with selectors: {user_sel}, {pass_sel}, {submit_sel}")
                        break
                except Exception as e:
                    logger.debug(f"Selector attempt failed: {e}")
                    continue
            
            # If still not found, try to find any password input and text input in a form
            if not username_input or not password_input:
                try:
                    # Look for forms containing password inputs
                    forms = await page.query_selector_all('form')
                    for form in forms:
                        password_inputs = await form.query_selector_all('input[type="password"]')
                        text_inputs = await form.query_selector_all('input[type="text"]:not([type="hidden"])')
                        submit_buttons = await form.query_selector_all('button[type="submit"], input[type="submit"], button')
                        
                        if password_inputs and text_inputs:
                            username_input = text_inputs[0]
                            password_input = password_inputs[0]
                            if submit_buttons:
                                submit_button = submit_buttons[0]
                            else:
                                # Try to find submit button outside form
                                submit_button = await page.query_selector('button[type="submit"], input[type="submit"]')
                            logger.info("Found login form by searching forms")
                            break
                except Exception as e:
                    logger.debug(f"Form search failed: {e}")
            
            if not username_input or not password_input:
                # If we can't find login form, check if already logged in
                logger.info("Login form not found, checking if already logged in...")
                cookies = await context.cookies()
                weeCookie = None
                hero_session = None
                
                for cookie in cookies:
                    if cookie['name'] == 'weeCookie':
                        weeCookie = cookie['value']
                    elif cookie['name'] == '50hero_session':
                        hero_session = cookie['value']
                
                if weeCookie:
                    logger.info("Already logged in, extracting cookies...")
                    cookie_string = f"svr={target_url};weeCookie={weeCookie}"
                    return {
                        'cookie_string': cookie_string,
                        'weeCookie': weeCookie,
                        '50hero_session': hero_session,
                        'success': True,
                        'error': None
                    }
                else:
                    raise Exception("Could not find login form and no existing cookies found")
            
            # Fill in login form
            logger.info("Filling in login form...")
            await username_input.click()  # Focus the input
            await username_input.fill(username)
            await page.wait_for_timeout(300)
            
            await password_input.click()  # Focus the input
            await password_input.fill(password)
            await page.wait_for_timeout(500)
            
            # Click submit button (or press Enter if no button found)
            logger.info("Submitting login form...")
            if submit_button:
                await submit_button.click()
            else:
                # Press Enter on password field as fallback
                await password_input.press('Enter')
            
            # Wait for navigation or login completion
            # Look for indicators that login was successful
            try:
                # Wait for URL change or specific element that appears after login
                await page.wait_for_timeout(3000)
                
                # Wait for cookies to be set (check multiple times)
                max_attempts = 10
                for attempt in range(max_attempts):
                    cookies = await context.cookies()
                    weeCookie = None
                    hero_session = None
                    
                    for cookie in cookies:
                        if cookie['name'] == 'weeCookie':
                            weeCookie = cookie['value']
                        elif cookie['name'] == '50hero_session':
                            hero_session = cookie['value']
                    
                    if weeCookie:
                        logger.info(f"Successfully extracted cookies (attempt {attempt + 1})")
                        cookie_string = f"svr={target_url};weeCookie={weeCookie}"
                        return {
                            'cookie_string': cookie_string,
                            'weeCookie': weeCookie,
                            '50hero_session': hero_session,
                            'success': True,
                            'error': None
                        }
                    
                    if attempt < max_attempts - 1:
                        await page.wait_for_timeout(2000)
                
                # If we still don't have cookies, check for error messages
                page_content = await page.content()
                if 'error' in page_content.lower() or '失败' in page_content or '错误' in page_content:
                    # Try to extract error message
                    error_elements = await page.query_selector_all('.error, .alert, [class*="error"], [class*="alert"]')
                    error_msg = "Login failed - unknown error"
                    if error_elements:
                        error_msg = await error_elements[0].inner_text()
                    raise Exception(f"Login failed: {error_msg}")
                
                raise Exception("Login completed but cookies not found. Please check if login was successful.")
                
            except PlaywrightTimeoutError as e:
                raise Exception(f"Timeout waiting for login completion: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error extracting cookies: {str(e)}")
        return {
            'cookie_string': None,
            'weeCookie': None,
            '50hero_session': None,
            'success': False,
            'error': str(e)
        }
    finally:
        if browser:
            try:
                await browser.close()
            except:
                pass


async def extract_cookies_interactive(page_url: Optional[str] = None, timeout: int = 300) -> Dict[str, Optional[str]]:
    """
    Interactive cookie extraction - opens a browser for user to log in manually,
    then extracts cookies after login is detected.
    
    Args:
        page_url: Optional URL to navigate to (defaults to game URL)
        timeout: Maximum time to wait for user to complete login (seconds)
    
    Returns:
        Dictionary containing extracted cookies (same format as extract_cookies)
    """
    browser: Optional[Browser] = None
    try:
        async with async_playwright() as p:
            # Launch browser in non-headless mode so user can interact
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            
            url = page_url or GAME_URL
            logger.info(f"Opening browser for manual login: {url}")
            # Use 'load' instead of 'networkidle' for better compatibility
            try:
                await page.goto(url, wait_until="load", timeout=60000)
            except PlaywrightTimeoutError as e:
                logger.warning(f"Load timeout, trying with domcontentloaded: {e}")
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # Wait for user to log in manually
            logger.info("Waiting for user to complete login...")
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                cookies = await context.cookies()
                weeCookie = None
                hero_session = None
                
                for cookie in cookies:
                    if cookie['name'] == 'weeCookie':
                        weeCookie = cookie['value']
                    elif cookie['name'] == '50hero_session':
                        hero_session = cookie['value']
                
                if weeCookie:
                    logger.info("Login detected, extracting cookies...")
                    cookie_string = f"svr={url};weeCookie={weeCookie}"
                    await browser.close()
                    return {
                        'cookie_string': cookie_string,
                        'weeCookie': weeCookie,
                        '50hero_session': hero_session,
                        'success': True,
                        'error': None
                    }
                
                await asyncio.sleep(2)
            
            await browser.close()
            raise Exception(f"Timeout: No cookies detected after {timeout} seconds. Please ensure you completed the login.")
            
    except Exception as e:
        logger.error(f"Error in interactive cookie extraction: {str(e)}")
        if browser:
            try:
                await browser.close()
            except:
                pass
        return {
            'cookie_string': None,
            'weeCookie': None,
            '50hero_session': None,
            'success': False,
            'error': str(e)
        }

async def open_browser_with_cookies(cookie_string: str, game_url: Optional[str] = None) -> Dict[str, Optional[str]]:
    """
    Open a browser with stored cookies to login to a game account.
    This is similar to making a request to home with cookies, but opens a browser window.
    
    Args:
        cookie_string: Cookie string in format "svr=...;weeCookie=..."
        game_url: Optional game URL (defaults to extracted from cookie_string or GAME_URL)
    
    Returns:
        Dictionary containing:
        - 'success': Boolean indicating success
        - 'error': Error message if failed
        - 'url': URL that was opened
    """
    browser: Optional[Browser] = None
    try:
        # Parse cookie string to extract URL and cookies
        # Format: "svr=http://s2.hero.9wee.com;weeCookie=..."
        cookie_parts = cookie_string.split(';')
        if not cookie_parts:
            raise Exception("Invalid cookie string format")
        
        # Extract server URL from first part
        svr_part = cookie_parts[0].strip()
        if not svr_part.startswith('svr='):
            raise Exception("Cookie string must start with 'svr='")
        
        target_url = svr_part.split('=', 1)[1].strip()
        if game_url:
            target_url = game_url
        
        # Parse cookies
        cookies_to_set = []
        weeCookie_value = None
        hero_session_value = None
        
        for part in cookie_parts:
            part = part.strip()
            if '=' in part:
                name, value = part.split('=', 1)
                name = name.strip()
                value = value.strip()
                
                if name == 'svr':
                    continue  # Skip svr, we already extracted it
                elif name == 'weeCookie':
                    weeCookie_value = value
                elif name == '50hero_session':
                    hero_session_value = value
                
                # Create cookie dict for Playwright
                # Extract domain from URL
                from urllib.parse import urlparse
                parsed_url = urlparse(target_url)
                domain = parsed_url.netloc
                
                cookie_dict = {
                    'name': name,
                    'value': value,
                    'domain': domain,
                    'path': '/'
                }
                cookies_to_set.append(cookie_dict)
        
        if not weeCookie_value:
            raise Exception("weeCookie not found in cookie string")
        
        # Use persistent context to keep browser open after function returns
        import tempfile
        import os
        user_data_dir = tempfile.mkdtemp(prefix="playwright_browser_")
        
        # Start playwright without context manager to keep browser alive
        p = await async_playwright().start()
        context_id = f"{target_url}_{time.time()}"
        
        try:
            # Launch browser with persistent context - this keeps the browser open
            # even after the function returns
            context = await p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=False,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--disable-gpu',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=site-per-process',
                    '--ignore-certificate-errors',
                    '--allow-running-insecure-content'
                ],
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                ignore_https_errors=True,
                java_script_enabled=True,
                viewport={'width': 1920, 'height': 1080},
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
            )
            
            # Store references to keep browser alive
            with _context_lock:
                _active_browser_contexts[context_id] = {
                    'playwright': p,
                    'context': context,
                    'user_data_dir': user_data_dir
                }
            
            # Get the first page (persistent context creates one automatically)
            pages = context.pages
            if pages:
                page = pages[0]
            else:
                page = await context.new_page()
            
            # Navigate to home page first to set domain context
            home_url = target_url.rstrip('/')
            logger.info(f"Opening browser with cookies to: {home_url}")
            
            try:
                await page.goto(home_url, wait_until="load", timeout=60000)
            except PlaywrightTimeoutError as e:
                logger.warning(f"Load timeout, trying with domcontentloaded: {e}")
                await page.goto(home_url, wait_until="domcontentloaded", timeout=60000)
            
            # Set cookies after navigating to the domain
            if cookies_to_set:
                await context.add_cookies(cookies_to_set)
                logger.info(f"Set {len(cookies_to_set)} cookies for domain {domain}")
                
                # Reload page to apply cookies
                await page.reload(wait_until="load", timeout=60000)
            
            # Wait a bit for page to fully load
            await page.wait_for_timeout(2000)
            
            logger.info(f"Browser opened successfully. URL: {page.url}")
            logger.info(f"Browser will stay open - user data directory: {user_data_dir}")
            logger.info(f"Browser context stored with ID: {context_id}")
            
            # Don't close the context or playwright - let browser stay open
            # The browser will remain open as long as the references are kept
            return {
                'success': True,
                'error': None,
                'url': page.url
            }
        except Exception as e:
            # Only cleanup on error
            with _context_lock:
                if context_id in _active_browser_contexts:
                    del _active_browser_contexts[context_id]
            try:
                await p.stop()
            except:
                pass
            raise
            
    except Exception as e:
        logger.error(f"Error opening browser with cookies: {str(e)}")
        if browser:
            try:
                await browser.close()
            except:
                pass
        return {
            'success': False,
            'error': str(e),
            'url': None
        }

