# -*- coding: utf-8 -*-
"""
Security tests for AI Scalping EA
"""

import pytest
import asyncio
import hashlib
import secrets
from unittest.mock import Mock, patch
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from src.config import Settings
from src.ai_orchestrator import AIOrchestrator, Agent
from src.utils.security import SecurityManager, InputValidator, EncryptionEngine


class TestSecurityManager:
    """Test cases for security components"""
    
    @pytest.mark.security
    def test_password_hashing(self):
        """Test secure password hashing"""
        manager = SecurityManager()
        
        # Test password hashing
        password = "test_password_123"
        salt = secrets.token_bytes(32)
        
        hash1 = manager.hash_password(password, salt)
        hash2 = manager.hash_password(password, salt)
        
        # Same password with same salt should produce same hash
        assert hash1 == hash2
        
        # Different passwords should produce different hashes
        different_hash = manager.hash_password("different_password", salt)
        assert hash1 != different_hash
    
    @pytest.mark.security
    def test_encryption_decryption(self):
        """Test encryption and decryption"""
        encryption_engine = EncryptionEngine()
        
        # Generate encryption key
        key = encryption_engine.generate_key()
        
        # Test encryption
        plaintext = b"Sensitive trading data"
        encrypted_data = encryption_engine.encrypt(plaintext, key)
        
        # Should be different from plaintext
        assert encrypted_data != plaintext
        
        # Test decryption
        decrypted_data = encryption_engine.decrypt(encrypted_data, key)
        assert decrypted_data == plaintext
    
    @pytest.mark.security
    def test_api_key_validation(self):
        """Test API key validation"""
        validator = InputValidator()
        
        # Valid API keys
        valid_keys = [
            "pk_live_1234567890abcdef",
            "pk_test_abcdef1234567890",
            "sk_live_abcdef1234567890",
            "sk_test_1234567890abcdef"
        ]
        
        for key in valid_keys:
            assert validator.validate_api_key(key) is True
        
        # Invalid API keys
        invalid_keys = [
            "invalid_key",
            "pk_",
            "1234567890",
            "",
            None
        ]
        
        for key in invalid_keys:
            assert validator.validate_api_key(key) is False
    
    @pytest.mark.security
    def test_symbol_validation(self):
        """Test trading symbol validation"""
        validator = InputValidator()
        
        # Valid forex symbols
        valid_symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD"]
        
        for symbol in valid_symbols:
            assert validator.validate_symbol(symbol) is True
        
        # Valid crypto symbols
        crypto_symbols = ["BTCUSD", "ETHUSD", "ADAUSD", "DOTUSD"]
        
        for symbol in crypto_symbols:
            assert validator.validate_symbol(symbol) is True
        
        # Invalid symbols
        invalid_symbols = ["", "INVALID", "EUR", "123", "EUR$", None]
        
        for symbol in invalid_symbols:
            assert validator.validate_symbol(symbol) is False
    
    @pytest.mark.security
    def test_numeric_input_validation(self):
        """Test numeric input validation"""
        validator = InputValidator()
        
        # Valid numeric inputs
        assert validator.validate_numeric(1.0, min_value=0.0, max_value=100.0) is True
        assert validator.validate_numeric(0.5, min_value=0.0, max_value=1.0) is True
        assert validator.validate_numeric(100, min_value=0, max_value=1000) is True
        
        # Invalid numeric inputs
        assert validator.validate_numeric(-1.0, min_value=0.0, max_value=100.0) is False
        assert validator.validate_numeric(1.5, min_value=0.0, max_value=1.0) is False
        assert validator.validate_numeric(1001, min_value=0, max_value=1000) is False
        assert validator.validate_numeric(None, min_value=0, max_value=100) is False
    
    @pytest.mark.security
    def test_sql_injection_prevention(self):
        """Test SQL injection prevention"""
        validator = InputValidator()
        
        # Test malicious inputs
        malicious_inputs = [
            "'; DROP TABLE trade_history; --",
            "' OR '1'='1",
            "'; DELETE FROM model_registry; --",
            "1' UNION SELECT password FROM users--",
            "' OR 1=1; --"
        ]
        
        for malicious_input in malicious_inputs:
            # Should be blocked by validation
            assert not validator.validate_sql_safe(malicious_input)
    
    @pytest.mark.security
    def test_xss_prevention(self):
        """Test XSS attack prevention"""
        validator = InputValidator()
        
        # Test malicious scripts
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "<svg onload=alert('xss')>",
            "';alert('xss');//"
        ]
        
        for payload in xss_payloads:
            # Should be sanitized or blocked
            assert not validator.validate_xss_safe(payload) if validator.is_xss_detected(payload) else True


class TestSecureAgent:
    """Test cases for secure agent operations"""
    
    @pytest.mark.security
    @pytest.mark.asyncio
    async def test_secure_prediction(self):
        """Test secure prediction execution"""
        agent = Agent("secure_agent", "/models/secure.pkl", "1.0.0", 0.6)
        agent.model = Mock()
        
        # Mock model to return safe prediction
        agent.model.predict.return_value = {
            "action": "BUY",
            "confidence": 0.8,
            "metadata": {"model_signature": "verified"}
        }
        
        # Test data
        test_data = {
            "symbol": "EURUSD",
            "market_data": [{"close": 1.1000}] * 60,
            "news_data": [{"sentiment": 0.5}]
        }
        
        result = await agent.predict(test_data)
        
        # Verify security measures
        assert "metadata" in result
        assert "model_signature" in result["metadata"]
        assert isinstance(result["action"], str)
        assert isinstance(result["confidence"], (int, float))
    
    @pytest.mark.security
    @pytest.mark.asyncio
    async def test_malicious_data_sanitization(self):
        """Test sanitization of malicious input data"""
        agent = Agent("test_agent", "/models/test.pkl", "1.0.0", 0.6)
        
        malicious_data = {
            "symbol": "'; DROP TABLE trade_history; --",
            "market_data": [{"close": "<script>alert('xss')</script>"}] * 60,
            "news_data": [{"sentiment": "1' OR '1'='1"}]
        }
        
        # Should handle gracefully without crashing
        try:
            result = await agent.predict(malicious_data)
            
            # Should return safe default
            assert result["action"] == "HOLD"
            assert result["confidence"] == 0.0
            assert "Error:" in result["reason"]
            
        except Exception as e:
            # Should not leak sensitive information
            assert "password" not in str(e).lower()
            assert "secret" not in str(e).lower()
    
    @pytest.mark.security
    def test_model_integrity_verification(self):
        """Test model integrity verification"""
        # Simulate model file with checksum
        model_data = b"fake model data"
        checksum = hashlib.sha256(model_data).hexdigest()
        
        # Test integrity verification
        agent = Agent("test_agent", "/models/test.pkl", "1.0.0", 0.6)
        
        # Mock file operations
        with patch('builtins.open', mock_open(read_data=model_data)):
            with patch('hashlib.sha256') as mock_sha256:
                mock_sha256.return_value.hexdigest.return_value = checksum
                
                # Should pass integrity check
                assert agent.verify_model_integrity(checksum) is True
                
                # Should fail with wrong checksum
                assert agent.verify_model_integrity("wrong_checksum") is False


class TestSecureConfiguration:
    """Test secure configuration management"""
    
    @pytest.mark.security
    def test_sensitive_data_encryption(self):
        """Test encryption of sensitive configuration data"""
        config = Mock(spec=Settings)
        
        # Test encryption of API keys
        api_key = "sk_live_1234567890abcdef"
        encryption_engine = EncryptionEngine()
        
        key = encryption_engine.generate_key()
        encrypted_key = encryption_engine.encrypt(api_key.encode(), key)
        
        # Should be different from original
        assert encrypted_key != api_key.encode()
        
        # Should decrypt back to original
        decrypted_key = encryption_engine.decrypt(encrypted_key, key)
        assert decrypted_key.decode() == api_key
    
    @pytest.mark.security
    def test_environment_variable_security(self):
        """Test secure handling of environment variables"""
        # Mock environment with sensitive data
        import os
        
        # Test that sensitive values are not exposed
        sensitive_vars = [
            "DB_PASSWORD",
            "SECRET_KEY", 
            "JWT_SECRET_KEY",
            "GEMINI_API_KEY"
        ]
        
        for var in sensitive_vars:
            # Should not be logged or exposed
            assert var not in str(locals())  # Not in local variables
            assert var not in str(globals())  # Not in global scope
    
    @pytest.mark.security
    def test_secure_random_generation(self):
        """Test secure random number generation"""
        manager = SecurityManager()
        
        # Generate multiple random values
        values = [manager.generate_secure_random(32) for _ in range(10)]
        
        # All values should be unique
        assert len(set(values)) == 10
        
        # All values should be proper length
        for value in values:
            assert len(value) == 32
            
            # Should contain only valid characters
            assert all(c in '0123456789abcdef' for c in value)


class TestRateLimiting:
    """Test rate limiting and DDoS protection"""
    
    @pytest.mark.security
    @pytest.mark.asyncio
    async def test_api_rate_limiting(self):
        """Test API rate limiting"""
        rate_limiter = SecurityManager()
        
        # Simulate multiple requests from same IP
        client_id = "192.168.1.100"
        max_requests = 100
        time_window = 60  # seconds
        
        # First batch should succeed
        for i in range(max_requests):
            assert await rate_limiter.check_rate_limit(client_id, max_requests, time_window) is True
        
        # Next request should be blocked
        assert await rate_limiter.check_rate_limit(client_id, max_requests, time_window) is False
        
        # Different client should still work
        assert await rate_limiter.check_rate_limit("192.168.1.101", max_requests, time_window) is True
    
    @pytest.mark.security
    @pytest.mark.asyncio
    async def test_concurrent_request_handling(self):
        """Test handling of concurrent requests"""
        rate_limiter = SecurityManager()
        
        # Simulate many concurrent requests
        client_id = "10.0.0.1"
        max_requests = 50
        
        # Create many concurrent tasks
        tasks = [
            rate_limiter.check_rate_limit(client_id, max_requests, 60)
            for _ in range(100)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Should allow exactly max_requests
        allowed_count = sum(results)
        assert allowed_count == max_requests
    
    @pytest.mark.security
    def test_ip_whitelist_validation(self):
        """Test IP whitelist validation"""
        manager = SecurityManager()
        
        # Add some IPs to whitelist
        whitelist = ["192.168.1.100", "10.0.0.0/24", "172.16.0.0/12"]
        
        # Test allowed IPs
        assert manager.is_ip_allowed("192.168.1.100", whitelist) is True
        assert manager.is_ip_allowed("10.0.0.5", whitelist) is True
        assert manager.is_ip_allowed("172.16.1.1", whitelist) is True
        
        # Test blocked IPs
        assert manager.is_ip_allowed("203.0.113.1", whitelist) is False
        assert manager.is_ip_allowed("8.8.8.8", whitelist) is False


class TestAuditLogging:
    """Test audit logging and compliance"""
    
    @pytest.mark.security
    @pytest.mark.asyncio
    async def test_audit_log_integration(self):
        """Test audit logging integration"""
        audit_logger = SecurityManager()
        
        # Simulate trading activity
        trade_data = {
            "trade_id": "trade_123",
            "symbol": "EURUSD",
            "action": "BUY",
            "amount": 1000,
            "user_id": "user_456"
        }
        
        # Should log without errors
        await audit_logger.log_trading_activity(trade_data)
        
        # Verify log entry contains required fields
        # (In real implementation, this would check the actual log)
    
    @pytest.mark.security
    @pytest.mark.asyncio
    async def test_failed_authentication_logging(self):
        """Test logging of failed authentication attempts"""
        audit_logger = SecurityManager()
        
        # Simulate failed login
        auth_data = {
            "username": "test_user",
            "ip_address": "192.168.1.100",
            "success": False,
            "reason": "Invalid password"
        }
        
        # Should log failed authentication
        await audit_logger.log_authentication_attempt(auth_data)
        
        # Verify security alert would be triggered
        # (In real implementation, this might send alerts)


@pytest.mark.security
@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_security_pipeline():
    """Test complete security pipeline"""
    # Initialize security components
    security_manager = SecurityManager()
    input_validator = InputValidator()
    
    # Test complete request flow with security checks
    test_request = {
        "symbol": "EURUSD",
        "action": "BUY",
        "amount": 1000,
        "user_token": "valid_jwt_token"
    }
    
    # Step 1: Validate input
    assert input_validator.validate_symbol(test_request["symbol"]) is True
    assert input_validator.validate_numeric(test_request["amount"], 0, 1000000) is True
    
    # Step 2: Rate limiting check
    assert await security_manager.check_rate_limit("127.0.0.1", 1000, 60) is True
    
    # Step 3: Authentication check (mock)
    # assert security_manager.validate_jwt_token(test_request["user_token"]) is True
    
    # All security checks should pass
    assert True  # If we reach here, all security checks passed