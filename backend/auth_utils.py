import os
import jwt
import smtplib
import string
import random
from datetime import datetime, timedelta
from typing import Optional
from email.mime.text import MIMEText
from email_validator import validate_email, EmailNotValidError
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from log import setup_logging

# Setup logging
logger = setup_logging()

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 120  # 120 hours
ACCESS_TOKEN_EXPIRE_MINUTES = ACCESS_TOKEN_EXPIRE_HOURS * 60  # Convert to minutes for backward compatibility

# Email Configuration - will be initialized after .env is loaded
# These are set as module-level variables but will be refreshed when needed
def _get_smtp_config():
    """Get SMTP configuration from environment variables"""
    return {
        'server': os.getenv("SMTP_SERVER", "smtp.gmail.com"),
        'port': int(os.getenv("SMTP_PORT", "587")),
        'username': os.getenv("SMTP_USERNAME"),
        'password': os.getenv("SMTP_PASSWORD")
    }

# Initialize at module load time
_smtp_config = _get_smtp_config()
SMTP_SERVER = _smtp_config['server']
SMTP_PORT = _smtp_config['port']
SMTP_USERNAME = _smtp_config['username']
SMTP_PASSWORD = _smtp_config['password']

# Log SMTP configuration status will be done lazily when send_email is first called
# to ensure .env file has been loaded

# Security
security = HTTPBearer()

# Global variables that will be set by main.py
user_table = None

def set_user_table(user_table_client):
    """Set the user table client from main.py"""
    global user_table
    user_table = user_table_client

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token"""
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return username
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

def send_email(to_email, subject, html_body):
    """Send email using SMTP
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        html_body: HTML body content
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Validate that html_body is provided
        if not html_body:
            logger.error("html_body must be provided")
            return False
        
        # Read credentials lazily in case they were set after module import
        smtp_username = os.getenv("SMTP_USERNAME") or SMTP_USERNAME
        smtp_password = os.getenv("SMTP_PASSWORD") or SMTP_PASSWORD
        
        if not smtp_username or not smtp_password:
            logger.warning("SMTP credentials not configured, skipping email send")
            return False
            
        smtp_server = os.getenv("SMTP_SERVER", SMTP_SERVER)
        smtp_port = int(os.getenv("SMTP_PORT", SMTP_PORT))
        
        # Create HTML message
        msg = MIMEText(html_body, 'html', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = smtp_username
        msg['To'] = to_email
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_username, smtp_password)
        text = msg.as_string()
        # Send email to the recipient only
        server.sendmail(smtp_username, [to_email], text)
        server.quit()
        
        logger.info(f"Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False

def validate_email_address(email: str):
    """Validate email address"""
    try:
        v = validate_email(email)
        return True
    except EmailNotValidError as e:
        raise HTTPException(status_code=400, detail=str(e))

def generate_random_password(length: int = 10) -> str:
    """Generate a random password"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def check_user_exists(email: str) -> bool:
    """Check if user exists in the database"""
    try:
        entity = user_table.get_entity(partition_key=email, row_key='0')
        return True
    except Exception:
        return False

def create_user_account(email: str, password: str, expiration_days: int = 30) -> dict:
    """Create a new user account (player type only).
    
    Note: Admin accounts must be created manually in Azure Table Storage.
    This function always creates 'player' type accounts.
    """
    expiration = (datetime.now() + timedelta(days=expiration_days)).strftime('%Y-%m-%d')
    entity = {
        'PartitionKey': email,
        'RowKey': '0',
        'password': password,
        'expiration': expiration,
        'user_type': 'player',  # Always 'player' - admin accounts must be created manually
        'disabled': False
    }
    user_table.create_entity(entity=entity)
    return entity

def verify_user_credentials(email: str, password: str) -> dict:
    """Verify user credentials and return user entity"""
    try:
        entity = user_table.get_entity(partition_key=email, row_key='0')
        if entity['password'] == password:
            # Check if account is disabled
            if entity.get('disabled', False):
                raise HTTPException(status_code=401, detail="Account disabled")
            
            # Check expiration only for player accounts (admin accounts don't expire)
            user_type = entity.get('user_type', 'player')
            if user_type == 'player':
                # Check if expiration field exists and is valid
                expiration = entity.get('expiration')
                if expiration and expiration < datetime.now().strftime('%Y-%m-%d'):
                    raise HTTPException(status_code=401, detail="Account expired")
            
            return entity
        else:
            raise HTTPException(status_code=401, detail="账号或密码错误")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error for email {email}: {str(e)}")
        raise HTTPException(status_code=401, detail="账号或密码错误")
