import os

class Config:
    # 1. Fallback to a local database URL if the Railway environment variable isn't injected
    DATABASE_URL = os.environ.get(
        "DATABASE_URL", 
        "postgresql://postgres:postgres@localhost:5432/gm_simulator"
    )
    
    # 2. Convert standard 'postgres://' protocol to 'postgresql://' if injected by older configurations
    if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        
    # 3. Seasonal Configs (Handy to avoid hardcoding years across your 11 scripts)
    CURRENT_SEASON = int(os.environ.get("CURRENT_SEASON", 2026))
    
    # 4. Request configurations for the MLB API
    MLB_API_BASE_URL = "https://statsapi.mlb.com/api/v1"
    
    # 5. Debug Mode
    DEBUG = os.environ.get("DEBUG", "False").lower() in ("true", "1", "t")

# Instantiate configuration so you can import it easily
config = Config()
