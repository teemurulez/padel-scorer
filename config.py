import os
import secrets

class Config:
    """Flask configuration"""

    # In production, SECRET_KEY must be set via environment variable
    # In development (FLASK_ENV=development or FLASK_DEBUG=1), a random key is generated
    _secret_key = os.environ.get('SECRET_KEY')
    _is_development = (
        os.environ.get('FLASK_ENV') == 'development' or
        os.environ.get('FLASK_DEBUG') == '1' or
        os.environ.get('TESTING') == '1'
    )

    if _secret_key:
        SECRET_KEY = _secret_key
    elif _is_development:
        # Generate a random key for development (changes on restart, but that's fine for dev)
        SECRET_KEY = secrets.token_hex(32)
    else:
        raise RuntimeError(
            "SECRET_KEY environment variable must be set in production. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )

    # Database path: configurable via DATABASE_PATH env var for Railway volume
    # Default: instance/padel.db (local development)
    DATABASE = os.environ.get('DATABASE_PATH', os.path.join('instance', 'padel.db'))

    # Session security settings
    SESSION_COOKIE_SECURE = not _is_development  # HTTPS only in production
    SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access
    SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF protection for cookies

    # Demo mode: read-only admin access for demonstrations
    # Set DEMO_PASSWORD env var to enable (leave unset to disable)
    DEMO_PASSWORD = os.environ.get('DEMO_PASSWORD')

    # Admin setup token: Required to create the first admin account
    # This prevents unauthorized admin creation if database is reset
    # Set ADMIN_SETUP_TOKEN env var in production
    ADMIN_SETUP_TOKEN = os.environ.get('ADMIN_SETUP_TOKEN')
