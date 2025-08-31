#!/usr/bin/env python3
"""
Healthcare Agent Audit Module

This module provides audit logging functionality for healthcare operations,
ensuring compliance with healthcare regulatory requirements and maintaining
complete audit trails for all system activities.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path


class AuditLogger:
    """
    Healthcare-compliant audit logger for tracking all system activities.
    
    This logger ensures that all healthcare-related actions are properly
    documented with timestamps, user information, and action details for
    regulatory compliance and security auditing.
    """
    
    def __init__(self, log_path: str = "./data/logs/audit.log"):
        """
        Initialize the audit logger.
        
        Args:
            log_path (str): Path to the audit log file
        """
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Configure logging
        self.logger = logging.getLogger('healthcare_audit')
        self.logger.setLevel(logging.INFO)
        
        # Create file handler if it doesn't exist
        if not self.logger.handlers:
            handler = logging.FileHandler(self.log_path)
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S UTC'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def log_action(self, 
                   action: str, 
                   user_id: Optional[str] = None,
                   patient_id: Optional[str] = None,
                   details: Optional[Dict[str, Any]] = None,
                   level: str = "INFO") -> None:
        """
        Log a healthcare system action with full audit trail.
        
        Args:
            action (str): Description of the action performed
            user_id (str, optional): ID of the user performing the action
            patient_id (str, optional): ID of the patient affected (if applicable)
            details (dict, optional): Additional details about the action
            level (str): Log level (INFO, WARNING, ERROR, CRITICAL)
        
        Example:
            audit_logger.log_action(
                action="Patient record accessed",
                user_id="dr_smith_123",
                patient_id="patient_456",
                details={"record_type": "medical_history", "access_reason": "routine_checkup"}
            )
        """
        
        # Create audit entry
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": action,
            "user_id": user_id,
            "patient_id": patient_id,
            "session_id": os.environ.get('SESSION_ID'),
            "ip_address": os.environ.get('CLIENT_IP'),
            "details": details or {},
            "compliance_level": "healthcare_audit"
        }
        
        # Convert to JSON for structured logging
        audit_json = json.dumps(audit_entry, separators=(',', ':'))
        
        # Log based on level
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(f"AUDIT: {audit_json}")
        
        # Also log to console in development
        if os.environ.get('APP_ENV') == 'development':
            print(f"[AUDIT] {action} - User: {user_id} - Patient: {patient_id}")


# Global audit logger instance
_audit_logger = None


def get_audit_logger() -> AuditLogger:
    """
    Get the global audit logger instance.
    
    Returns:
        AuditLogger: The global audit logger instance
    """
    global _audit_logger
    if _audit_logger is None:
        log_path = os.environ.get('AUDIT_LOG_PATH', './data/logs/audit.log')
        _audit_logger = AuditLogger(log_path)
    return _audit_logger


def log_action(action: str, 
               user_id: Optional[str] = None,
               patient_id: Optional[str] = None,
               details: Optional[Dict[str, Any]] = None,
               level: str = "INFO") -> None:
    """
    Convenience function to log an audit action using the global logger.
    
    This is the main function that should be used throughout the healthcare
    application for audit logging.
    
    Args:
        action (str): Description of the action performed
        user_id (str, optional): ID of the user performing the action  
        patient_id (str, optional): ID of the patient affected (if applicable)
        details (dict, optional): Additional details about the action
        level (str): Log level (INFO, WARNING, ERROR, CRITICAL)
    
    Example:
        from backend.utils.audit import log_action
        
        log_action(
            action="Patient prescription updated",
            user_id="dr_johnson_789", 
            patient_id="patient_123",
            details={"medication": "aspirin", "dosage": "81mg daily"}
        )
    """
    logger = get_audit_logger()
    logger.log_action(action, user_id, patient_id, details, level)


if __name__ == "__main__":
    # Example usage and testing
    print("Healthcare Agent Audit Module - Testing")
    
    # Test basic logging
    log_action(
        action="System startup",
        details={"version": "1.0.0", "environment": "testing"}
    )
    
    # Test patient-related action
    log_action(
        action="Patient record created", 
        user_id="test_user_001",
        patient_id="test_patient_001",
        details={"record_type": "initial_intake", "department": "emergency"}
    )
    
    # Test error logging
    log_action(
        action="Database connection failed",
        details={"error": "connection_timeout", "retry_count": 3},
        level="ERROR"
    )
    
    print("Audit logging test completed. Check the log file for entries.")
