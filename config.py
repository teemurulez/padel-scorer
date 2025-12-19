import os

class Config:
    """Flask configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DATABASE = os.path.join('instance', 'padel.db')
