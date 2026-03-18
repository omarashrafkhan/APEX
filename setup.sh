# Create python vnenv
python -m venv .venv

# Activate it
.\.venv\Scripts\activate

# Install request for fecthing html web page
pip install requests

# Install Langraph this provides nodes and routing iirc
pip install -U langgraph

# Install Langchain this porvides llm and some other stuff
pip install -U langchain

# Installing the OpenAI integration
pip install -U "langchain[openai]"

# Installing the Anthropic integration
pip install -U langchain-anthropic

# Install Google Gemini integration
pip install -U "langchain[google-genai]"

# install deepagents
pip install deepagents 

# install dotenv 
pip install python-dotenv

# for interactive cli, not good as ink but for now better than nothing 
pip install rich prompt_toolkit

# ionstall selenium and beautifulsoup for web scraping
pip install selenium beautifulsoup4