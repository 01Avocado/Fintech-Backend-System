import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Load environment variables from .env file
load_dotenv()

# ==================== SHARD 1 (Odd User IDs) ====================
Database_URL_1 = os.getenv("DATABASE_URL_1")
engine1 = create_engine(Database_URL_1)
SessionLocal1 = sessionmaker(autocommit=False, autoflush=False, bind=engine1)

# ==================== SHARD 2 (Even User IDs) ====================
Database_URL_2 = os.getenv("DATABASE_URL_2")
engine2 = create_engine(Database_URL_2)
SessionLocal2 = sessionmaker(autocommit=False, autoflush=False, bind=engine2)

# Declarative Base for models
Base = declarative_base()
