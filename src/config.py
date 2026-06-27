# src/config.py
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:pass@localhost:5432/dbname")
