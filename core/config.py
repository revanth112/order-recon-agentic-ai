# core/config.py - Load environment variables and global settings
import os
from dotenv import load_dotenv

load_dotenv()

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

# Database
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "./data/order_recon.db")

# Reconciliation guardrail thresholds
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.8"))
PRICE_TOLERANCE_PCT = float(os.getenv("PRICE_TOLERANCE_PCT", "0.05"))
QTY_TOLERANCE_PCT = float(os.getenv("QTY_TOLERANCE_PCT", "0.05"))

# RAG
RULES_DIR = os.getenv("RULES_DIR", "./rules")
RAG_PERSIST_DIR = os.getenv("RAG_PERSIST_DIR", "./data/rules_index")

# App
ENV = os.getenv("ENV", "dev")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
