# 💬 Chatbot template

A simple Streamlit app that shows how to build a chatbot using OpenAI's GPT-3.5.

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://chatbot-template.streamlit.app/)

### How to run it on your own machine

1. Install the requirements

   ```
   $ pip install -r requirements.txt
   ```

2. Run the app

   ```
   $ streamlit run streamlit_app.py
   ```

3. Provide your OpenAI API key by one of these methods:

   - Add an `OPENAI_API_KEY` entry to `.streamlit/secrets.toml`.
   - Set an `OPENAI_API_KEY` environment variable.
   - Enter the key manually when the app prompts for it.

   The app checks Streamlit secrets first, then environment variables, and only
   prompts for manual entry if a key isn't found.

### Conversation history

Chat messages are stored in a local SQLite database (`chat_history.db`). Use the sidebar controls to reset the conversation or export the history as a JSON file.
