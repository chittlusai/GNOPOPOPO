import os
from google import genai

api_key = os.environ.get("GEMINI_API_KEY", "").strip()
client = genai.Client(api_key=api_key)

for m in client.models.list():
    if "generateContent" in m.supported_actions:
        print(m.name)
