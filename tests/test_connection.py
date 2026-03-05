import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    base_url=os.getenv("AZURE_OPENAI_ENDPOINT"),
)

resp = client.chat.completions.create(
    model=os.getenv("AZURE_CHAT_DEPLOYMENT", "gpt-4o"),
    messages=[{"role": "user", "content": "say hello"}],
)
print(resp.choices[0].message.content)
