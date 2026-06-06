#!/usr/bin/env python3
# Secret Rotation Strategy for STRATUM_LIGHT

import os
import logging
import json
import time
import uuid
import base64
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Set up logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s|%(levelname)s|%(message)s')
logger = logging.getLogger(__name__)

class SecretRotationManager:
    """Manages automatic rotation of production secrets"""
    
    SECRET_TYPES = ["API_KEY", "ENCRYPTION_KEY", "JWT_SECRET", "WEBHOOK_TOKEN"]
    DEFAULT_ROTATION_DAYS = {
        "API_KEY": 30,
        "ENCRYPTION_KEY": 90,
        "JWT_SECRET": 30,
        "WEBHOOK_TOKEN": 60
    }
    
    def __init__(self, secrets_file: str = "secrets.json", master_key_env: str = "STRATUM_MASTER_KEY"):
        """
        Initialize the secret rotation manager
        
        Args:
            secrets_file: Path to the encrypted secrets file
            master_key_env: Environment variable name for the master key
        """
        self.secrets_file = secrets_file
        self.master_key_env = master_key_env
        self.master_key = os.getenv(master_key_env)
        
        if not self.master_key:
            logger.warning(f"Master key environment variable {master_key_env} not set")
            self.cipher = None
        else:
            # Derive a key from the master key
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'stratum_light_salt',  # In production, use a secure random salt
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(self.master_key.encode()))
            self.cipher = Fernet(key)
    
    def _load_secrets(self) -> Dict:
        """Load secrets from the encrypted file"""
        if not self.cipher:
            logger.error("Cannot load secrets: cipher not initialized")
            return {}
            
        try:
            if os.path.exists(self.secrets_file):
                with open(self.secrets_file, "rb") as f:
                    encrypted_data = f.read()
                    decrypted_data = self.cipher.decrypt(encrypted_data)
                    return json.loads(decrypted_data)
            else:
                logger.warning(f"Secrets file {self.secrets_file} not found, creating new")
                return {}
        except Exception as e:
            logger.error(f"Failed to load secrets: {str(e)}")
            return {}
    
    def _save_secrets(self, secrets: Dict) -> bool:
        """Save secrets to the encrypted file"""
        if not self.cipher:
            logger.error("Cannot save secrets: cipher not initialized")
            return False
            
        try:
            encrypted_data = self.cipher.encrypt(json.dumps(secrets).encode())
            with open(self.secrets_file, "wb") as f:
                f.write(encrypted_data)
            logger.info(f"Secrets saved to {self.secrets_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save secrets: {str(e)}")
            return False
    
    def get_secret(self, secret_type: str, name: str) -> Optional[str]:
        """
        Get a secret value, checking if rotation is needed
        
        Args:
            secret_type: Type of secret (API_KEY, ENCRYPTION_KEY, etc.)
            name: Name of the secret
            
        Returns:
            The secret value or None if not found
        """
        if secret_type not in self.SECRET_TYPES:
            logger.error(f"Invalid secret type: {secret_type}")
            return None
            
        secrets = self._load_secrets()
        key = f"{secret_type}:{name}"
        
        if key not in secrets:
            logger.warning(f"Secret {key} not found")
            return None
            
        secret_data = secrets[key]
        
        # Check if rotation is needed
        if self._needs_rotation(secret_data):
            logger.info(f"Secret {key} needs rotation")
            self._rotate_secret(secret_type, name)
            secrets = self._load_secrets()  # Reload after rotation
            
        return secrets.get(key, {}).get("value")
    
    def _needs_rotation(self, secret_data: Dict) -> bool:
        """Check if a secret needs rotation based on its expiry"""
        if "expiry" not in secret_data:
            return True
            
        expiry = datetime.fromisoformat(secret_data["expiry"])
        return datetime.now() >= expiry
    
    def _rotate_secret(self, secret_type: str, name: str) -> bool:
        """
        Rotate a secret
        
        Args:
            secret_type: Type of secret
            name: Name of the secret
            
        Returns:
            True if rotation was successful
        """
        secrets = self._load_secrets()
        key = f"{secret_type}:{name}"
        
        # Generate new secret value
        new_value = self._generate_secret(secret_type)
        
        # Calculate expiry date
        rotation_days = self.DEFAULT_ROTATION_DAYS.get(secret_type, 30)
        expiry = datetime.now() + timedelta(days=rotation_days)
        
        # Store old value for transition period
        old_value = None
        if key in secrets:
            old_value = secrets[key].get("value")
        
        # Update secret
        secrets[key] = {
            "value": new_value,
            "created": datetime.now().isoformat(),
            "expiry": expiry.isoformat(),
            "previous": old_value,
            "type": secret_type
        }
        
        # Save updated secrets
        success = self._save_secrets(secrets)
        if success:
            logger.info(f"Secret {key} rotated successfully")
        
        return success
    
    def _generate_secret(self, secret_type: str) -> str:
        """Generate a new secret value based on type"""
        if secret_type == "ENCRYPTION_KEY":
            return Fernet.generate_key().decode()
        else:
            # Generate a UUID-based secret
            return f"{secret_type}_{uuid.uuid4().hex}_{int(time.time())}"
    
    def create_secret(self, secret_type: str, name: str, value: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Create a new secret
        
        Args:
            secret_type: Type of secret
            name: Name of the secret
            value: Optional value (generated if not provided)
            
        Returns:
            Tuple of (success, value)
        """
        if secret_type not in self.SECRET_TYPES:
            logger.error(f"Invalid secret type: {secret_type}")
            return False, None
            
        secrets = self._load_secrets()
        key = f"{secret_type}:{name}"
        
        if key in secrets:
            logger.warning(f"Secret {key} already exists")
            return False, None
            
        # Generate or use provided value
        secret_value = value if value else self._generate_secret(secret_type)
        
        # Calculate expiry date
        rotation_days = self.DEFAULT_ROTATION_DAYS.get(secret_type, 30)
        expiry = datetime.now() + timedelta(days=rotation_days)
        
        # Store secret
        secrets[key] = {
            "value": secret_value,
            "created": datetime.now().isoformat(),
            "expiry": expiry.isoformat(),
            "previous": None,
            "type": secret_type
        }
        
        # Save updated secrets
        success = self._save_secrets(secrets)
        if success:
            logger.info(f"Secret {key} created successfully")
            return True, secret_value
        else:
            return False, None
    
    def list_secrets(self) -> Dict:
        """List all secrets (without values)"""
        secrets = self._load_secrets()
        result = {}
        
        for key, data in secrets.items():
            result[key] = {
                "created": data.get("created"),
                "expiry": data.get("expiry"),
                "type": data.get("type"),
                "has_previous": data.get("previous") is not None
            }
            
        return result
    
    def check_rotation_status(self) -> Dict:
        """Check rotation status of all secrets"""
        secrets = self._load_secrets()
        result = {
            "total": len(secrets),
            "needs_rotation": 0,
            "expired": 0,
            "healthy": 0,
            "details": {}
        }
        
        now = datetime.now()
        
        for key, data in secrets.items():
            if "expiry" not in data:
                status = "unknown"
                result["needs_rotation"] += 1
            else:
                expiry = datetime.fromisoformat(data["expiry"])
                if now >= expiry:
                    status = "expired"
                    result["expired"] += 1
                elif now >= expiry - timedelta(days=7):
                    status = "needs_rotation"
                    result["needs_rotation"] += 1
                else:
                    status = "healthy"
                    result["healthy"] += 1
                    
            result["details"][key] = {
                "status": status,
                "expiry": data.get("expiry")
            }
            
        return result

def main():
    """Command-line interface for secret rotation"""
    import argparse
    
    parser = argparse.ArgumentParser(description="STRATUM_LIGHT Secret Rotation Manager")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Create command
    create_parser = subparsers.add_parser("create", help="Create a new secret")
    create_parser.add_argument("--type", required=True, choices=SecretRotationManager.SECRET_TYPES, help="Secret type")
    create_parser.add_argument("--name", required=True, help="Secret name")
    create_parser.add_argument("--value", help="Secret value (generated if not provided)")
    
    # Get command
    get_parser = subparsers.add_parser("get", help="Get a secret value")
    get_parser.add_argument("--type", required=True, choices=SecretRotationManager.SECRET_TYPES, help="Secret type")
    get_parser.add_argument("--name", required=True, help="Secret name")
    
    # List command
    subparsers.add_parser("list", help="List all secrets")
    
    # Status command
    subparsers.add_parser("status", help="Check rotation status")
    
    # Rotate command
    rotate_parser = subparsers.add_parser("rotate", help="Rotate a secret")
    rotate_parser.add_argument("--type", required=True, choices=SecretRotationManager.SECRET_TYPES, help="Secret type")
    rotate_parser.add_argument("--name", required=True, help="Secret name")
    
    args = parser.parse_args()
    
    manager = SecretRotationManager()
    
    if args.command == "create":
        success, value = manager.create_secret(args.type, args.name, args.value)
        if success:
            print(f"Secret created: {args.type}:{args.name}")
            print(f"Value: {value}")
        else:
            print("Failed to create secret")
            
    elif args.command == "get":
        value = manager.get_secret(args.type, args.name)
        if value:
            print(f"Secret: {args.type}:{args.name}")
            print(f"Value: {value}")
        else:
            print(f"Secret {args.type}:{args.name} not found")
            
    elif args.command == "list":
        secrets = manager.list_secrets()
        print(f"Found {len(secrets)} secrets:")
        for key, data in secrets.items():
            print(f"- {key}")
            print(f"  Created: {data['created']}")
            print(f"  Expires: {data['expiry']}")
            
    elif args.command == "status":
        status = manager.check_rotation_status()
        print(f"Secret rotation status:")
        print(f"- Total: {status['total']}")
        print(f"- Healthy: {status['healthy']}")
        print(f"- Needs rotation: {status['needs_rotation']}")
        print(f"- Expired: {status['expired']}")
        
    elif args.command == "rotate":
        success = manager._rotate_secret(args.type, args.name)
        if success:
            print(f"Secret {args.type}:{args.name} rotated successfully")
        else:
            print(f"Failed to rotate secret {args.type}:{args.name}")
            
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
