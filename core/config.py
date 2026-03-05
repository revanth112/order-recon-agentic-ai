# core/config.py - Load environment variables and global settings
import os
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

# ------------------------------------------------------------------
# Azure OpenAI client (OpenAI SDK v1.x + Azure AI Foundry base_url)
# ------------------------------------------------------------------
AZURE_OPENAI_API_KEY  = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv(
    "AZURE_OPENAI_ENDPOINT",
    "https://YOUR-RESOURCE.cognitiveservices.azure.com/"
)
AZURE_OPENAI_API_VERSION  = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
# Deployment / model name as set in Azure AI Foundry
OPENAI_MODEL = os.getenv("AZURE_CHAT_DEPLOYMENT", "gpt-4o")
AZURE_EMBED_DEPLOYMENT = os.getenv("AZURE_EMBED_DEPLOYMENT", "text-embedding-ada-002")

# Shared Azure OpenAI client instance - import this anywhere you need the LLM
# Use a placeholder key when none is configured so that the module can be imported
# safely in environments without Azure credentials (e.g. unit tests). Actual API
# calls will still fail with an auth error if a real key is absent.
azure_openai_client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY or "no-api-key-configured",
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_version=AZURE_OPENAI_API_VERSION, 
)

# ------------------------------------------------------------------
# Database
# ------------------------------------------------------------------
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "./data/order_recon.db")

# ------------------------------------------------------------------
# Reconciliation guardrail thresholds
# ------------------------------------------------------------------
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.8"))
PRICE_TOLERANCE_PCT  = float(os.getenv("PRICE_TOLERANCE_PCT",  "0.05"))
QTY_TOLERANCE_PCT    = float(os.getenv("QTY_TOLERANCE_PCT",    "0.05"))

# Per-vendor tolerance overrides (price_pct, qty_pct).
# Falls back to PRICE_TOLERANCE_PCT / QTY_TOLERANCE_PCT for unknown vendors.
VENDOR_TOLERANCES: dict = {
    "V-001": {"price_pct": 0.02, "qty_pct": 0.05},   # Acme Supplies Ltd - 2% price, 5% qty
    "V-002": {"price_pct": 0.05, "qty_pct": 0.10},   # GlobalTech - 5% price, 10% qty
    "V-003": {"price_pct": 0.01, "qty_pct": 0.03},   # FastParts - strict 1% price, 3% qty
    "V-004": {"price_pct": 0.05, "qty_pct": 0.05},
    "V-005": {"price_pct": 0.05, "qty_pct": 0.05},
    "V-006": {"price_pct": 0.03, "qty_pct": 0.05},
    "V-007": {"price_pct": 0.05, "qty_pct": 0.05},
    "V-008": {"price_pct": 0.05, "qty_pct": 0.08},
    "V-009": {"price_pct": 0.05, "qty_pct": 0.05},
    "V-010": {"price_pct": 0.04, "qty_pct": 0.05},
}

# ------------------------------------------------------------------
# RAG
# ------------------------------------------------------------------
RULES_DIR       = os.getenv("RULES_DIR",       "./rules")
RAG_PERSIST_DIR = os.getenv("RAG_PERSIST_DIR", "./data/rules_index")

# ------------------------------------------------------------------
# App
# ------------------------------------------------------------------
ENV       = os.getenv("ENV",       "dev")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
