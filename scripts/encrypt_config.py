#!/usr/bin/env python3
# Script to encrypt the light_config.json file

import os
import json
import sys
from cryptography.fernet import Fernet

def encrypt_config(config_path, output_path, key=None):
    """
    Encrypt a configuration file using Fernet symmetric encryption
    
    Args:
        config_path: Path to the plaintext config file
        output_path: Path to save the encrypted config file
        key: Optional encryption key (generates a new one if not provided)
        
    Returns:
        The encryption key used
    """
    # Generate or use provided key
    if key is None:
        key = Fernet.generate_key()
    elif isinstance(key, str):
        key = key.encode()
        
    cipher = Fernet(key)
    
    # Read the plaintext config
    try:
        with open(config_path, 'r') as f:
            config_data = f.read()
    except Exception as e:
        print(f"Error reading config file: {e}")
        return None
    
    # Encrypt the config
    try:
        encrypted_data = cipher.encrypt(config_data.encode())
    except Exception as e:
        print(f"Error encrypting config: {e}")
        return None
    
    # Write the encrypted config
    try:
        with open(output_path, 'wb') as f:
            f.write(encrypted_data)
        print(f"Encrypted configuration saved to {output_path}")
    except Exception as e:
        print(f"Error writing encrypted config: {e}")
        return None
    
    return key.decode() if isinstance(key, bytes) else key

def main():
    if len(sys.argv) < 3:
        print("Usage: python encrypt_config.py <input_file> <output_file> [encryption_key]")
        return
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    key = sys.argv[3] if len(sys.argv) > 3 else None
    
    result_key = encrypt_config(input_file, output_file, key)
    
    if result_key:
        print(f"Encryption successful. Key: {result_key}")
        print("Set this key as LIGHT_CONFIG_KEY in your environment or .env file")
    else:
        print("Encryption failed")

if __name__ == "__main__":
    main()
