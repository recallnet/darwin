"""
Security utilities for Darwin API.

Provides functions for:
- Password hashing and verification (bcrypt)
- JWT token generation and validation
- Token decoding and claims extraction
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "development-secret-key-change-in-production")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password to hash

    Returns:
        str: Hashed password

    Example:
        >>> hashed = hash_password("mypassword123")
        >>> print(hashed)
        $2b$12$...
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hashed password.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against

    Returns:
        bool: True if password matches, False otherwise

    Example:
        >>> hashed = hash_password("mypassword123")
        >>> verify_password("mypassword123", hashed)
        True
        >>> verify_password("wrongpassword", hashed)
        False
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.

    Args:
        data: Payload data to encode in the token (e.g., {"sub": user_id, "team_id": team_id})
        expires_delta: Optional custom expiration time

    Returns:
        str: Encoded JWT token

    Example:
        >>> token = create_access_token({"sub": "user123", "team_id": "team456"})
        >>> print(token)
        eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
    """
    to_encode = data.copy()

    # Set expiration time
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "iat": datetime.utcnow()})

    # Encode JWT
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT access token.

    Args:
        token: JWT token to decode

    Returns:
        Optional[Dict[str, Any]]: Decoded token payload if valid, None if invalid

    Example:
        >>> token = create_access_token({"sub": "user123"})
        >>> payload = decode_access_token(token)
        >>> print(payload["sub"])
        user123
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def get_token_user_id(token: str) -> Optional[str]:
    """
    Extract user ID from JWT token.

    Args:
        token: JWT token

    Returns:
        Optional[str]: User ID (sub claim) if valid token, None otherwise

    Example:
        >>> token = create_access_token({"sub": "user123"})
        >>> user_id = get_token_user_id(token)
        >>> print(user_id)
        user123
    """
    payload = decode_access_token(token)
    if payload:
        return payload.get("sub")
    return None


def get_token_team_id(token: str) -> Optional[str]:
    """
    Extract team ID from JWT token.

    Args:
        token: JWT token

    Returns:
        Optional[str]: Team ID if present in token, None otherwise

    Example:
        >>> token = create_access_token({"sub": "user123", "team_id": "team456"})
        >>> team_id = get_token_team_id(token)
        >>> print(team_id)
        team456
    """
    payload = decode_access_token(token)
    if payload:
        return payload.get("team_id")
    return None


def create_invitation_token() -> str:
    """
    Create a secure random token for team invitations.

    Returns:
        str: Random hex token (64 characters)

    Example:
        >>> token = create_invitation_token()
        >>> len(token)
        64
    """
    import secrets

    return secrets.token_hex(32)
