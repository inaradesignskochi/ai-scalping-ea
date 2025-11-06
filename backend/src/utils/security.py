# -*- coding: utf-8 -*-
"""
Security utilities for AI Scalping EA
"""

import hashlib
import secrets
import re
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import jwt
import logging


class SecurityManager:
    """Central security management class"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.rate_limits: Dict[str, Dict[str, Any]] = {}
        self.failed_attempts: Dict[str, List[datetime]] = {}
        
    def hash_password(self, password: str, salt: bytes) -> str:
        """Hash password with salt using PBKDF2"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        hash_value = kdf.derive(password.encode())
        return hash_value.hex()
    
    def generate_secure_random(self, length: int = 32) -> str:
        """Generate cryptographically secure random string"""
        return secrets.token_hex(length)
    
    async def check_rate_limit(self, client_id: str, max_requests: int, 
                             time_window: int) -> bool:
        """Check and update rate limiting"""
        now = datetime.utcnow()
        
        if client_id not in self.rate_limits:
            self.rate_limits[client_id] = {
                'requests': [],
                'blocked_until': None
            }
        
        client_data = self.rate_limits[client_id]
        
        # Check if temporarily blocked
        if client_data['blocked_until'] and now < client_data['blocked_until']:
            return False
        
        # Clean old requests
        cutoff = now - timedelta(seconds=time_window)
        client_data['requests'] = [
            req_time for req_time in client_data['requests']
            if req_time > cutoff
        ]
        
        # Check limit
        if len(client_data['requests']) >= max_requests:
            # Block for 1 hour if consistently over limit
            client_data['blocked_until'] = now + timedelta(hours=1)
            self.logger.warning(f"Rate limit exceeded for {client_id}")
            return False
        
        # Record request
        client_data['requests'].append(now)
        return True
    
    def is_ip_allowed(self, ip_address: str, whitelist: List[str]) -> bool:
        """Check if IP is in whitelist"""
        # Simple IP matching (in production, use proper IP range matching)
        for allowed in whitelist:
            if allowed.endswith('/24'):
                # Handle subnet notation
                network = allowed.split('/')[0]
                base_ip = network.rsplit('.', 1)[0]
                if ip_address.startswith(base_ip):
                    return True
            elif ip_address == allowed:
                return True
        return False
    
    async def log_trading_activity(self, trade_data: Dict[str, Any]):
        """Log trading activity for audit"""
        self.logger.info(f"Trading activity: {trade_data}")
    
    async def log_authentication_attempt(self, auth_data: Dict[str, Any]):
        """Log authentication attempts"""
        self.logger.warning(f"Auth attempt: {auth_data}")


class InputValidator:
    """Input validation and sanitization"""
    
    # Trading symbol patterns
    FOREX_PATTERN = re.compile(r'^[A-Z]{6}$')
    CRYPTO_PATTERN = re.compile(r'^[A-Z]{3}USD$')
    
    # API key patterns
    API_KEY_PATTERN = re.compile(r'^(pk|sk)_(live|test)_[a-zA-Z0-9]{32}$')
    
    def validate_symbol(self, symbol: str) -> bool:
        """Validate trading symbol"""
        if not symbol or not isinstance(symbol, str):
            return False
        
        symbol = symbol.upper()
        
        # Check forex pairs
        if self.FOREX_PATTERN.match(symbol):
            return True
        
        # Check crypto pairs
        if self.CRYPTO_PATTERN.match(symbol):
            return True
        
        return False
    
    def validate_api_key(self, api_key: str) -> bool:
        """Validate API key format"""
        if not api_key or not isinstance(api_key, str):
            return False
        
        return self.API_KEY_PATTERN.match(api_key) is not None
    
    def validate_numeric(self, value: Any, min_value: Optional[float] = None,
                        max_value: Optional[float] = None) -> bool:
        """Validate numeric input with bounds"""
        try:
            num_value = float(value)
            
            if min_value is not None and num_value < min_value:
                return False
            
            if max_value is not None and num_value > max_value:
                return False
            
            return True
        except (ValueError, TypeError):
            return False
    
    def validate_sql_safe(self, input_str: str) -> bool:
        """Check if input is SQL injection safe"""
        if not input_str:
            return True
        
        # Dangerous SQL patterns
        dangerous_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b)",
            r"(\b(UNION|JOIN|WHERE|AND|OR)\b)",
            r"(['\"];|--|\bEXEC\b|\bEXECUTE\b)",
            r"(\bINFORMATION_SCHEMA\b|\bUSER_TABLES\b)",
            r"(\bOR\b\s*['\"]?1['\"]?\s*=\s*['\"]?1)"
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, input_str, re.IGNORECASE):
                return False
        
        return True
    
    def is_xss_detected(self, input_str: str) -> bool:
        """Detect XSS patterns"""
        if not input_str:
            return False
        
        xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe[^>]*>",
            r"<object[^>]*>",
            r"<embed[^>]*>",
            r"vbscript:",
            r"expression\(",
            r"@import"
        ]
        
        for pattern in xss_patterns:
            if re.search(pattern, input_str, re.IGNORECASE):
                return True
        
        return False
    
    def validate_xss_safe(self, input_str: str) -> bool:
        """Check if input is XSS safe"""
        return not self.is_xss_detected(input_str)


class EncryptionEngine:
    """Encryption and decryption utilities"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate_key(self, password: Optional[str] = None) -> bytes:
        """Generate encryption key"""
        if password:
            # Derive key from password
            salt = secrets.token_bytes(16)
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            return key
        else:
            # Generate random key
            return Fernet.generate_key()
    
    def encrypt(self, data: bytes, key: bytes) -> bytes:
        """Encrypt data with Fernet"""
        try:
            fernet = Fernet(key)
            return fernet.encrypt(data)
        except Exception as e:
            self.logger.error(f"Encryption failed: {e}")
            raise
    
    def decrypt(self, encrypted_data: bytes, key: bytes) -> bytes:
        """Decrypt data with Fernet"""
        try:
            fernet = Fernet(key)
            return fernet.decrypt(encrypted_data)
        except Exception as e:
            self.logger.error(f"Decryption failed: {e}")
            raise


class JWTAuthenticator:
    """JWT token management"""
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.algorithm = 'HS256'
    
    def generate_token(self, payload: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Generate JWT token"""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(hours=24)
        
        payload.update({'exp': expire})
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None


# Global security instances
security_manager = SecurityManager()
input_validator = InputValidator()
encryption_engine = EncryptionEngine()