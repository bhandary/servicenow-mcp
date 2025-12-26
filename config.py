import os

class Config:
    """Application configuration."""
    
    # Flask configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # ServiceNow configuration
    SERVICENOW_INSTANCE_URL = os.getenv('SERVICENOW_INSTANCE_URL')
    SERVICENOW_USERNAME = os.getenv('SERVICENOW_USERNAME')
    SERVICENOW_PASSWORD = os.getenv('SERVICENOW_PASSWORD')
    
    # Server configuration
    PORT = int(os.getenv('PORT', 8000))
    HOST = os.getenv('HOST', '0.0.0.0')
    
    # Timeout settings
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', 300))