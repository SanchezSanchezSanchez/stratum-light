#!/usr/bin/env python3
# GDPR Test Data Anonymization for STRATUM_LIGHT

import re
import json
import logging
import hashlib
import random
import string
from typing import Dict, Any, List, Union, Optional
from datetime import datetime, timedelta

# Set up logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s|%(levelname)s|%(message)s')
logger = logging.getLogger(__name__)

class GDPRAnonymizer:
    """GDPR-compliant data anonymization for test environments"""
    
    # PII detection patterns
    PII_PATTERNS = {
        "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "phone": r'\b(?:\+\d{1,3}[- ]?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}\b',
        "ssn": r'\b\d{3}-\d{2}-\d{4}\b',
        "credit_card": r'\b(?:\d{4}[- ]?){3}\d{4}\b',
        "ip_address": r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
        "address": r'\b\d+\s+[A-Za-z0-9\s,]+(?:Avenue|Lane|Road|Boulevard|Drive|Street|Ave|Dr|Rd|Blvd|Ln|St)\.?\b',
        "name": r'\b(?:[A-Z][a-z]+\s+){1,2}[A-Z][a-z]+\b'
    }
    
    def __init__(self, salt: str = None, mode: str = "pseudonymize"):
        """
        Initialize the GDPR anonymizer
        
        Args:
            salt: Salt for hashing (random if not provided)
            mode: Anonymization mode ("pseudonymize", "redact", or "synthetic")
        """
        self.salt = salt or ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        self.mode = mode
        logger.info(f"GDPR Anonymizer initialized in {mode} mode")
    
    def anonymize_data(self, data: Any) -> Any:
        """
        Anonymize data based on type
        
        Args:
            data: Data to anonymize
            
        Returns:
            Anonymized data
        """
        if isinstance(data, dict):
            return self._anonymize_dict(data)
        elif isinstance(data, list):
            return self._anonymize_list(data)
        elif isinstance(data, str):
            return self._anonymize_string(data)
        else:
            # Numbers, booleans, None, etc. are not anonymized
            return data
    
    def _anonymize_dict(self, data: Dict) -> Dict:
        """Anonymize a dictionary"""
        result = {}
        for key, value in data.items():
            # Check if key suggests PII
            pii_type = self._detect_pii_field(key)
            
            if pii_type:
                result[key] = self._anonymize_value(value, pii_type)
            else:
                # Recursively anonymize value
                result[key] = self.anonymize_data(value)
                
        return result
    
    def _anonymize_list(self, data: List) -> List:
        """Anonymize a list"""
        return [self.anonymize_data(item) for item in data]
    
    def _anonymize_string(self, data: str) -> str:
        """Anonymize a string by detecting and replacing PII"""
        result = data
        
        # Check for each PII pattern
        for pii_type, pattern in self.PII_PATTERNS.items():
            result = re.sub(
                pattern,
                lambda m: self._anonymize_value(m.group(0), pii_type),
                result
            )
            
        return result
    
    def _anonymize_value(self, value: Any, pii_type: str) -> Any:
        """
        Anonymize a value based on PII type and mode
        
        Args:
            value: Value to anonymize
            pii_type: Type of PII
            
        Returns:
            Anonymized value
        """
        if not isinstance(value, str):
            return value
            
        if self.mode == "redact":
            return f"[REDACTED {pii_type}]"
            
        elif self.mode == "pseudonymize":
            # Create deterministic but irreversible pseudonym
            hash_input = f"{value}{self.salt}{pii_type}"
            hash_value = hashlib.sha256(hash_input.encode()).hexdigest()
            
            if pii_type == "email":
                return f"user_{hash_value[:8]}@example.com"
            elif pii_type == "phone":
                return f"+1-555-{hash_value[:3]}-{hash_value[3:7]}"
            elif pii_type == "ssn":
                return f"XXX-XX-{hash_value[:4]}"
            elif pii_type == "credit_card":
                return f"XXXX-XXXX-XXXX-{hash_value[:4]}"
            elif pii_type == "ip_address":
                return f"192.168.{hash_value[:1]}.{hash_value[1:3]}"
            elif pii_type == "address":
                return f"123 Example St., Test City, TS 12345"
            elif pii_type == "name":
                return f"Test User {hash_value[:4]}"
            else:
                return f"[ANONYMIZED:{hash_value[:8]}]"
                
        elif self.mode == "synthetic":
            # Generate synthetic but realistic-looking data
            if pii_type == "email":
                domains = ["example.com", "test.org", "sample.net"]
                return f"user_{random.randint(1000, 9999)}@{random.choice(domains)}"
            elif pii_type == "phone":
                return f"+1-555-{random.randint(100, 999)}-{random.randint(1000, 9999)}"
            elif pii_type == "ssn":
                return f"123-45-{random.randint(1000, 9999)}"
            elif pii_type == "credit_card":
                return f"4111-1111-1111-{random.randint(1000, 9999)}"
            elif pii_type == "ip_address":
                return f"192.168.{random.randint(0, 255)}.{random.randint(0, 255)}"
            elif pii_type == "address":
                streets = ["Main St", "Oak Ave", "Maple Rd", "Pine Ln"]
                return f"{random.randint(100, 999)} {random.choice(streets)}, Test City, TS 12345"
            elif pii_type == "name":
                first_names = ["John", "Jane", "Alex", "Sam", "Taylor"]
                last_names = ["Doe", "Smith", "Johnson", "Brown", "Test"]
                return f"{random.choice(first_names)} {random.choice(last_names)}"
            else:
                return f"[SYNTHETIC DATA]"
        else:
            return value
    
    def _detect_pii_field(self, field_name: str) -> Optional[str]:
        """
        Detect if a field name suggests PII
        
        Args:
            field_name: Field name to check
            
        Returns:
            PII type if detected, None otherwise
        """
        field_lower = field_name.lower()
        
        if any(x in field_lower for x in ["email", "mail"]):
            return "email"
        elif any(x in field_lower for x in ["phone", "mobile", "cell", "tel"]):
            return "phone"
        elif any(x in field_lower for x in ["ssn", "social", "security"]):
            return "ssn"
        elif any(x in field_lower for x in ["card", "credit", "payment"]):
            return "credit_card"
        elif any(x in field_lower for x in ["ip", "ipaddress"]):
            return "ip_address"
        elif any(x in field_lower for x in ["address", "street", "city", "zip"]):
            return "address"
        elif any(x in field_lower for x in ["name", "first", "last", "user"]):
            return "name"
        else:
            return None

class TestDataAnonymizer:
    """Test data anonymization for GDPR compliance"""
    
    def __init__(self, gdpr_mode: bool = True, anonymization_mode: str = "pseudonymize"):
        """
        Initialize the test data anonymizer
        
        Args:
            gdpr_mode: Whether to enable GDPR mode
            anonymization_mode: Anonymization mode
        """
        self.gdpr_mode = gdpr_mode
        self.anonymizer = GDPRAnonymizer(mode=anonymization_mode) if gdpr_mode else None
        logger.info(f"Test Data Anonymizer initialized (GDPR mode: {gdpr_mode})")
    
    def anonymize_request(self, request_data: Dict) -> Dict:
        """
        Anonymize request data
        
        Args:
            request_data: Request data to anonymize
            
        Returns:
            Anonymized request data
        """
        if not self.gdpr_mode:
            return request_data
            
        return self.anonymizer.anonymize_data(request_data)
    
    def anonymize_response(self, response_data: Dict) -> Dict:
        """
        Anonymize response data
        
        Args:
            response_data: Response data to anonymize
            
        Returns:
            Anonymized response data
        """
        if not self.gdpr_mode:
            return response_data
            
        return self.anonymizer.anonymize_data(response_data)
    
    def anonymize_file(self, input_file: str, output_file: str) -> bool:
        """
        Anonymize a file
        
        Args:
            input_file: Input file path
            output_file: Output file path
            
        Returns:
            True if successful
        """
        if not self.gdpr_mode:
            logger.info("GDPR mode disabled, skipping file anonymization")
            return False
            
        try:
            with open(input_file, 'r') as f:
                data = json.load(f)
                
            anonymized_data = self.anonymizer.anonymize_data(data)
            
            with open(output_file, 'w') as f:
                json.dump(anonymized_data, f, indent=2)
                
            logger.info(f"File anonymized: {input_file} -> {output_file}")
            return True
        except Exception as e:
            logger.error(f"File anonymization failed: {str(e)}")
            return False
    
    def create_anonymized_test_data(self, template_file: str, output_file: str, count: int = 10) -> bool:
        """
        Create anonymized test data from a template
        
        Args:
            template_file: Template file path
            output_file: Output file path
            count: Number of records to generate
            
        Returns:
            True if successful
        """
        try:
            with open(template_file, 'r') as f:
                template = json.load(f)
                
            if isinstance(template, list):
                # Template is a list of records
                result = []
                for _ in range(count):
                    for record in template:
                        anonymized_record = self.anonymizer.anonymize_data(record.copy())
                        result.append(anonymized_record)
            else:
                # Template is a single record
                result = []
                for _ in range(count):
                    anonymized_record = self.anonymizer.anonymize_data(template.copy())
                    result.append(anonymized_record)
                    
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
                
            logger.info(f"Generated {len(result)} anonymized test records: {output_file}")
            return True
        except Exception as e:
            logger.error(f"Test data generation failed: {str(e)}")
            return False

# FastAPI middleware for request/response anonymization
class GDPRMiddleware:
    """FastAPI middleware for GDPR compliance"""
    
    def __init__(self, app, gdpr_mode: bool = True):
        """
        Initialize the GDPR middleware
        
        Args:
            app: FastAPI app
            gdpr_mode: Whether to enable GDPR mode
        """
        self.app = app
        self.anonymizer = TestDataAnonymizer(gdpr_mode=gdpr_mode)
        logger.info(f"GDPR Middleware initialized (GDPR mode: {gdpr_mode})")
    
    async def __call__(self, scope, receive, send):
        """Process a request/response cycle"""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
            
        # Create modified receive and send functions
        async def modified_receive():
            message = await receive()
            
            if message["type"] == "http.request" and self.anonymizer.gdpr_mode:
                # Anonymize request body
                body = message.get("body", b"")
                if body:
                    try:
                        data = json.loads(body.decode())
                        anonymized_data = self.anonymizer.anonymize_request(data)
                        message["body"] = json.dumps(anonymized_data).encode()
                    except:
                        # Not JSON or other error, leave as is
                        pass
                        
            return message
            
        async def modified_send(message):
            if message["type"] == "http.response.body" and self.anonymizer.gdpr_mode:
                # Anonymize response body
                body = message.get("body", b"")
                if body:
                    try:
                        data = json.loads(body.decode())
                        anonymized_data = self.anonymizer.anonymize_response(data)
                        message["body"] = json.dumps(anonymized_data).encode()
                    except:
                        # Not JSON or other error, leave as is
                        pass
                        
            await send(message)
            
        await self.app(scope, modified_receive, modified_send)

def main():
    """Command-line interface for test data anonymization"""
    import argparse
    
    parser = argparse.ArgumentParser(description="STRATUM_LIGHT Test Data Anonymizer")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Anonymize file command
    anonymize_parser = subparsers.add_parser("anonymize", help="Anonymize a file")
    anonymize_parser.add_argument("--input", required=True, help="Input file path")
    anonymize_parser.add_argument("--output", required=True, help="Output file path")
    anonymize_parser.add_argument("--mode", choices=["pseudonymize", "redact", "synthetic"], default="pseudonymize", help="Anonymization mode")
    
    # Generate test data command
    generate_parser = subparsers.add_parser("generate", help="Generate anonymized test data")
    generate_parser.add_argument("--template", required=True, help="Template file path")
    generate_parser.add_argument("--output", required=True, help="Output file path")
    generate_parser.add_argument("--count", type=int, default=10, help="Number of records to generate")
    generate_parser.add_argument("--mode", choices=["pseudonymize", "redact", "synthetic"], default="synthetic", help="Anonymization mode")
    
    args = parser.parse_args()
    
    if args.command == "anonymize":
        anonymizer = TestDataAnonymizer(gdpr_mode=True, anonymization_mode=args.mode)
        success = anonymizer.anonymize_file(args.input, args.output)
        if success:
            print(f"File anonymized: {args.input} -> {args.output}")
        else:
            print("File anonymization failed")
            
    elif args.command == "generate":
        anonymizer = TestDataAnonymizer(gdpr_mode=True, anonymization_mode=args.mode)
        success = anonymizer.create_anonymized_test_data(args.template, args.output, args.count)
        if success:
            print(f"Generated anonymized test data: {args.output}")
        else:
            print("Test data generation failed")
            
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
