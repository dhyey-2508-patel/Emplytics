import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)

try:
    models = client.models.list()
    print("Available Models:")
    for model in models:
        print(f"- {model.id}")
except Exception as e:
    print(f"Error fetching models: {e}")
