"""
Input validation utilities for user-provided data.

This module provides validation functions to prevent injection attacks
and ensure data integrity for user inputs.
"""
import re
from typing import Optional, List
from log import setup_logging

logger = setup_logging()

# Maximum lengths for various user inputs
MAX_COOKIE_LENGTH = 10000
MAX_ACCOUNT_NAME_LENGTH = 100
MAX_USERNAME_LENGTH = 255
MAX_URL_LENGTH = 2048

# Patterns for validation
# Cookie format: svr=<server>; weeCookie=<cookie_value>
COOKIE_PATTERN = re.compile(r'^svr=[^;]+;\s*weeCookie=[^;]+$')

def validate_cookie(cookie: Optional[str]) -> str:
    """
    Validate and sanitize user-provided cookie.

    Args:
        cookie: The cookie string to validate

    Returns:
        The validated and sanitized cookie

    Raises:
        ValueError: If cookie is invalid
    """
    if not cookie:
        raise ValueError("Cookie cannot be empty")

    if not isinstance(cookie, str):
        raise ValueError("Cookie must be a string")

    cookie = cookie.strip()

    # Check length
    if len(cookie) > MAX_COOKIE_LENGTH:
        raise ValueError(f"Cookie too long (max {MAX_COOKIE_LENGTH} characters)")

    # Check minimum required format (must contain svr= and weeCookie=)
    if 'svr=' not in cookie or 'weeCookie=' not in cookie:
        raise ValueError("Cookie must contain 'svr=' and 'weeCookie=' components")

    # Basic format validation
    parts = cookie.split(';')
    if len(parts) < 2:
        raise ValueError("Cookie must have at least two components separated by ';'")

    # Validate each component doesn't contain malicious characters
    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Check for suspicious patterns that might indicate injection attempts
        if any(char in part for char in ['\n', '\r', '\x00']):
            raise ValueError("Cookie contains invalid characters")

        # Check for SQL injection patterns (basic check)
        if any(pattern in part.lower() for pattern in ['--', '/*', '*/', 'xp_', 'sp_', 'exec ']):
            raise ValueError("Cookie contains potentially malicious content")

    return cookie


def validate_account_name(account_name: str) -> str:
    """
    Validate and sanitize account name.

    Args:
        account_name: The account name to validate

    Returns:
        The validated and sanitized account name

    Raises:
        ValueError: If account name is invalid
    """
    if not account_name:
        raise ValueError("Account name cannot be empty")

    if not isinstance(account_name, str):
        raise ValueError("Account name must be a string")

    account_name = account_name.strip()

    # Check length
    if len(account_name) > MAX_ACCOUNT_NAME_LENGTH:
        raise ValueError(f"Account name too long (max {MAX_ACCOUNT_NAME_LENGTH} characters)")

    if len(account_name) == 0:
        raise ValueError("Account name cannot be empty or only whitespace")

    # Check for suspicious patterns
    if any(char in account_name for char in ['\n', '\r', '\x00', '\t']):
        raise ValueError("Account name contains invalid characters")

    # Check for SQL injection patterns (basic check)
    if any(pattern in account_name.lower() for pattern in ['--', '/*', '*/', 'xp_', 'sp_', 'drop ', 'delete ', 'truncate ']):
        raise ValueError("Account name contains potentially malicious content")

    return account_name


def validate_username(username: str) -> str:
    """
    Validate and sanitize username (email/identifier).

    Args:
        username: The username to validate

    Returns:
        The validated and sanitized username

    Raises:
        ValueError: If username is invalid
    """
    if not username:
        raise ValueError("Username cannot be empty")

    if not isinstance(username, str):
        raise ValueError("Username must be a string")

    username = username.strip()

    # Check length
    if len(username) > MAX_USERNAME_LENGTH:
        raise ValueError(f"Username too long (max {MAX_USERNAME_LENGTH} characters)")

    if len(username) == 0:
        raise ValueError("Username cannot be empty or only whitespace")

    # Check for suspicious patterns
    if any(char in username for char in ['\n', '\r', '\x00', '\t']):
        raise ValueError("Username contains invalid characters")

    # Check for SQL injection patterns
    if any(pattern in username.lower() for pattern in ['--', '/*', '*/', 'xp_', 'sp_', "';", "' or ", "' and "]):
        raise ValueError("Username contains potentially malicious content")

    return username


def escape_for_azure_table_query(value: str) -> str:
    """
    Escape a string value for safe use in Azure Table Storage OData queries.

    According to Azure Table Storage documentation, single quotes must be escaped
    by doubling them (' '').

    Args:
        value: The string value to escape

    Returns:
        The escaped string safe for use in queries

    Raises:
        ValueError: If value contains characters that cannot be safely escaped
    """
    if not isinstance(value, str):
        raise ValueError("Value must be a string")

    # Check for other potentially dangerous characters in OData
    # While single quotes are the main concern, we should also warn about others
    dangerous_chars = ['\n', '\r', '\x00']
    if any(char in value for char in dangerous_chars):
        raise ValueError("Value contains invalid characters for query")

    # Escape single quotes by doubling them (Azure Table Storage requirement)
    escaped = value.replace("'", "''")

    logger.debug(f"Escaped value for Azure query: {value[:20]}... -> {escaped[:20]}...")
    return escaped


def validate_json_string(json_str: str, max_length: int = 10000) -> str:
    """
    Validate a JSON string for safety.

    Args:
        json_str: The JSON string to validate
        max_length: Maximum allowed length

    Returns:
        The validated JSON string

    Raises:
        ValueError: If JSON string is invalid
    """
    import json

    if not json_str:
        return "{}"

    if not isinstance(json_str, str):
        raise ValueError("JSON must be a string")

    if len(json_str) > max_length:
        raise ValueError(f"JSON string too long (max {max_length} characters)")

    # Try to parse it to ensure it's valid JSON
    try:
        json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {str(e)}")

    # Check for suspicious patterns
    if any(char in json_str for char in ['\x00']):
        raise ValueError("JSON contains invalid characters")

    return json_str


def sanitize_log_message(message: str) -> str:
    """
    Sanitize a message before logging to remove sensitive information.

    Args:
        message: The message to sanitize

    Returns:
        The sanitized message
    """
    if not message:
        return ""

    # Remove potential cookie values from logs
    import re
    # Pattern to match weeCookie=<value>
    message = re.sub(r'weeCookie=[^;\s&]+', 'weeCookie=***REDACTED***', message)
    # Pattern to match svr= values
    message = re.sub(r'svr=[^;\s&]+', 'svr=***REDACTED***', message)

    return message
