from langchain_google_genai import ChatGoogleGenerativeAI
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

def getGeminiLLM():
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        temperature=0.1,
        google_api_key=os.getenv("VERTEX_API_KEY_OMAR")
    )

# Simple test to verify Gemini LLM is working
if __name__ == "__main__":
    llm = getGeminiLLM()
    response = llm.invoke("Write a 500 words essay on Google Gemin")
    print(response)