import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or '9658486e6fd4d8d00fa2dfd6df6dd3a9a479d0ec0564871f4dee941e96b21c1f'
    
    # Use SQLite for local development, PostgreSQL for production
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        if db_url.startswith('postgresql://') and '+psycopg' not in db_url:
            db_url = db_url.replace('postgresql://', 'postgresql+psycopg://', 1)
        SQLALCHEMY_DATABASE_URI = db_url
    else:
        # Fallback to SQLite for local testing
        SQLALCHEMY_DATABASE_URI = 'sqlite:///skillsync.db'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    
    # Session config
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Flask-Login
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    
    # Flask-Mail
    MAIL_SERVER = os.environ.get('EMAIL_HOST') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('EMAIL_PORT') or 587)
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('EMAIL_USER') or 'chalagerianusha4@gmail.com'
    MAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD') or 'kotu fkgc ftbd kaxw'
    MAIL_DEFAULT_SENDER = ('SkillSync Nexus', 'chalagerianusha4@gmail.com')
    
    # Agora Config
    AGORA_APP_ID = os.environ.get('AGORA_APP_ID') or 'a4a03487d76d4a6c861bdab7c704d58b'
    AGORA_APP_CERTIFICATE = os.environ.get('AGORA_APP_CERTIFICATE') or 'f5b406d1f4d446d6a759c5818008ebc3'
    
    # Credit System
    INITIAL_CREDITS = 50
    CREDITS_30_MIN = 25
    CREDITS_1_HOUR = 50
    CREDITS_2_HOURS = 100
    MAX_LEARNING_HOURS = 2
    MAX_EXCHANGE_HOURS = 4
    MIN_EXCHANGE_HOURS = 1
    
    # Certificate threshold
    CERTIFICATE_CREDITS_THRESHOLD = 500
    
    # Upload config
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
