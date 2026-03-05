import os
from dotenv import load_dotenv
from openai import AzureOpenAI  # ← AzureOpenAI, not OpenAI

load_dotenv()

endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
api_key  = os.getenv("AZURE_OPENAI_API_KEY")
version  = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
model    = os.getenv("AZURE_CHAT_DEPLOYMENT", "gpt-4o")

print(f"Endpoint   : {endpoint}")
print(f"Deployment : {model}")
print(f"API version: {version}")

client = AzureOpenAI(
    api_key=api_key,
    azure_endpoint=endpoint,   # ← azure_endpoint, not base_url
    api_version=version,
)

resp = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": "say hello"}],
)
print("✅ Response:", resp.choices[0].message.content)
