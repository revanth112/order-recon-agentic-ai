# core/config.py - Load environment variables and global settings
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ------------------------------------------------------------------
# Azure OpenAI client (OpenAI SDK v1.x + Azure AI Foundry base_url)
# ------------------------------------------------------------------
AZURE_OPENAI_API_KEY  = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv(
    "AZURE_OPENAI_ENDPOINT",
    "https://YOUR-RESOURCE-NAME.openai.azure.com/openai/v1/"
)
AZURE_OPENAI_API_VERSION  = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
# Deployment / model name as set in Azure AI Foundry
OPENAI_MODEL = os.getenv("AZURE_CHAT_DEPLOYMENT", "gpt-4o")
AZURE_EMBED_DEPLOYMENT = os.getenv("AZURE_EMBED_DEPLOYMENT", "text-embedding-ada-002")

# Shared Azure OpenAI client instance - import this anywhere you need the LLM
# Use a placeholder key when none is configured so that the module can be imported
# safely in environments without Azure credentials (e.g. unit tests). Actual API
# calls will still fail with an auth error if a real key is absent.
azure_openai_client = OpenAI(
    api_key=AZURE_OPENAI_API_KEY or "no-api-key-configured",
    base_url=AZURE_OPENAI_ENDPOINT,
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
