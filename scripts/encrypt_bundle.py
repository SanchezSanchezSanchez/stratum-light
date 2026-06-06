#!/usr/bin/env python3
"""
STRATUM_LIGHT Bundle Encryption Tool

This script creates an encrypted archive of the STRATUM_LIGHT investor delivery bundle
with SHA-512 checksum verification.
"""

import os
import sys
import tarfile
import hashlib
import argparse
import getpass
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

def generate_key(password, salt=b'stratum_light_bundle'):
    """Generate encryption key from password."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key

def calculate_sha512(file_path):
    """Calculate SHA-512 checksum of a file."""
    sha512_hash = hashlib.sha512()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha512_hash.update(byte_block)
    return sha512_hash.hexdigest()

def create_archive(source_dir, output_file):
    """Create tar.gz archive of source directory."""
    with tarfile.open(output_file, "w:gz") as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir))
    
    print(f"Archive created: {output_file}")
    return output_file

def encrypt_file(input_file, output_file, key):
    """Encrypt a file using Fernet symmetric encryption."""
    fernet = Fernet(key)
    
    with open(input_file, "rb") as f:
        data = f.read()
    
    encrypted_data = fernet.encrypt(data)
    
    with open(output_file, "wb") as f:
        f.write(encrypted_data)
    
    print(f"Encrypted file created: {output_file}")
    return output_file

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="STRATUM_LIGHT Bundle Encryption Tool")
    parser.add_argument("--source", default="/home/ubuntu/stratum_light_bundle", 
                        help="Source directory to archive and encrypt")
    parser.add_argument("--output", default="/home/ubuntu/stratum_light_investor_bundle.enc", 
                        help="Output encrypted file")
    parser.add_argument("--password", help="Encryption password (will prompt if not provided)")
    args = parser.parse_args()
    
    # Ensure source directory exists
    source_dir = Path(args.source)
    if not source_dir.exists() or not source_dir.is_dir():
        print(f"Error: Source directory {source_dir} does not exist")
        return 1
    
    # Get password
    password = args.password
    if not password:
        password = getpass.getpass("Enter encryption password: ")
        confirm = getpass.getpass("Confirm encryption password: ")
        if password != confirm:
            print("Error: Passwords do not match")
            return 1
    
    # Create temporary archive
    temp_archive = f"{args.output}.tar.gz"
    create_archive(args.source, temp_archive)
    
    # Calculate SHA-512 checksum
    checksum = calculate_sha512(temp_archive)
    print(f"SHA-512 checksum: {checksum}")
    
    # Save checksum to file
    checksum_file = f"{args.output}.sha512"
    with open(checksum_file, "w") as f:
        f.write(f"{checksum}  {os.path.basename(args.output)}\n")
    
    print(f"Checksum saved to: {checksum_file}")
    
    # Generate encryption key
    key = generate_key(password)
    
    # Encrypt archive
    encrypt_file(temp_archive, args.output, key)
    
    # Clean up temporary archive
    os.unlink(temp_archive)
    
    print("\nSTRATUM_LIGHT Investor Bundle created successfully!")
    print(f"Encrypted bundle: {args.output}")
    print(f"SHA-512 checksum: {checksum_file}")
    print("\nIMPORTANT: Store the password securely. It will be required to decrypt the bundle.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
