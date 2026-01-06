from pydantic import BaseModel
from typing import Optional, Union, List

class LoginRequest(BaseModel):
    username: str
    password: str

class GoogleLoginRequest(BaseModel):
    token: str  # Google OAuth access token

class Account(BaseModel):
    account_name: str
    cookie: str
    hall_settings: Optional[dict] = None
    common_settings: Optional[dict] = None
    dungeon_settings: Optional[List[dict]] = None
    duel_dungeon_settings: Optional[List[dict]] = None

class RegisterRequest(BaseModel):
    email: str

class GameCommandRequest(BaseModel):
    account_name: str
    command: str

class AddAccountRequest(BaseModel):
    username: str
    account_name: str
    cookie: str
    hall_settings: Optional[dict] = None
    common_settings: Optional[dict] = None
    dungeon_settings: Optional[List[dict]] = None
    duel_dungeon_settings: Optional[List[dict]] = None
    game_id: Optional[str] = None  # Game account ID/username
    password: Optional[str] = None  # Game account password

class InfoRequest(BaseModel):
    account_name: str
    target_username: Optional[str] = None  # For admin operations

class HallCombatRequest(BaseModel):
    username: str
    account_names: Union[str, List[str]]  # Can be single account name or list of account names
    hall_name: str  # Name of the specific hall to challenge
    config: Optional[dict] = None  # Optionally allow config override

class HallCombatStreamRequest(BaseModel):
    account_names: Union[str, List[str]]  # Can be single account name or list of account names
    hall_name: Optional[str] = None  # Optional: target specific hall for individual challenge
    target_username: Optional[str] = None  # For admin operations
    skip_combat_count_check: Optional[bool] = True  # Skip combat count check (True for UI calls by default, False for backend jobs to enable check)

class ExtractCookiesRequest(BaseModel):
    username: str  # Game account username
    password: str  # Game account password
    url: Optional[str] = None  # Game URL (defaults to https://hero.9wee.com if not provided)
    timeout: Optional[int] = 60  # Timeout in seconds (default 60)

class ExtractCookiesInteractiveRequest(BaseModel):
    page_url: Optional[str] = None  # Optional URL to navigate to
    timeout: Optional[int] = 300  # Timeout in seconds (default 5 minutes)

class ExecuteJobRequest(BaseModel):
    job_id: str
    account_names: Optional[List[str]] = None  # Optional list of account names
    target_username: Optional[str] = None  # For admin operations

class OpenBrowserWithCookiesRequest(BaseModel):
    target_username: str  # Username of the account owner
    account_name: str  # Account name to open browser for
    game_url: Optional[str] = None  # Optional game URL (defaults to extracted from cookie)
    