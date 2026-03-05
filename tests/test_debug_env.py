import os
from dotenv import load_dotenv

# Load .env explicitly from the project root
load_dotenv()

print("=== ENV VALUES LOADED ===")
print(f"AZURE_OPENAI_API_KEY    : {os.getenv('AZURE_OPENAI_API_KEY', 'NOT SET')[:10]}...")
print(f"AZURE_OPENAI_ENDPOINT   : {os.getenv('AZURE_OPENAI_ENDPOINT', 'NOT SET')}")
print(f"AZURE_OPENAI_API_VERSION: {os.getenv('AZURE_OPENAI_API_VERSION', 'NOT SET')}")
print(f"AZURE_CHAT_DEPLOYMENT   : {os.getenv('AZURE_CHAT_DEPLOYMENT', 'NOT SET')}")
