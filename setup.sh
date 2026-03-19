# Create python vnenv
python -m venv .venv

# Activate it
.\.venv\Scripts\activate

# Install request for fecthing html web page
pip install requests langgraph langchain "langchain[openai]" langchain-anthropic "langchain[google-genai]" deepagents  python-dotenv rich prompt_toolkit selenium beautifulsoup4