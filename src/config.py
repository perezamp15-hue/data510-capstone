# src/config.py
import os
from dotenv import load_dotenv

load_dotenv()

# Railway maps its internal database link to this environment variable directly
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:pass@localhost:5432/dbname")
