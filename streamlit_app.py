import json
import sqlite3
import logging
from pathlib import Path
import streamlit as st
import openai
from openai import OpenAI

from assistant_tools import manage_todo, schedule_meeting, send_email


logger = logging.getLogger(__name__)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "schedule_meeting",
            "description": "Schedule a meeting given a topic and time",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Topic of the meeting"},
                    "time": {"type": "string", "description": "When the meeting takes place"},
                },
                "required": ["topic", "time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send a simple email",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient": {"type": "string", "description": "Email recipient"},
                    "subject": {"type": "string", "description": "Email subject"},
                    "body": {"type": "string", "description": "Email body"},
                },
                "required": ["recipient", "subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manage_todo",
            "description": "Add, list, or clear todo items",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "add, list, or clear tasks",
                    },
                    "task": {
                        "type": "string",
                        "description": "Task description (required for add)",
                    },
                },
                "required": ["action"],
            },
        },
    },
]

# Show title and description.
st.title("💬 Chatbot")
st.write(
    "This is a simple chatbot that uses OpenAI's GPT-3.5 model to generate responses. "
    "To use this app, you need to provide an OpenAI API key, which you can get [here](https://platform.openai.com/account/api-keys). "
    "You can also learn how to build this app step by step by [following our tutorial](https://docs.streamlit.io/develop/tutorials/llms/build-conversational-apps)."
)

# --- Persistence layer ----------------------------------------------------- #
DB_PATH = Path("chat_history.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT,
            content TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_tasks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def load_history():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role, content FROM messages")
    messages = [{"role": role, "content": content} for role, content in c.fetchall()]
    c.execute("SELECT task FROM admin_tasks")
    admin_tasks = [row[0] for row in c.fetchall()]
    conn.close()
    return messages, admin_tasks


def save_message(role: str, content: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO messages (role, content) VALUES (?, ?)",
        (role, content),
    )
    conn.commit()
    conn.close()


def clear_history():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM messages")
    c.execute("DELETE FROM admin_tasks")
    conn.commit()
    conn.close()
    st.session_state.messages = []
    st.session_state.admin_tasks = []


# Ask user for their OpenAI API key via `st.text_input`.
# Alternatively, you can store the API key in `./.streamlit/secrets.toml` and access it
# via `st.secrets`, see https://docs.streamlit.io/develop/concepts/connections/secrets-management
openai_api_key = st.text_input("OpenAI API Key", type="password")
if not openai_api_key:
    st.info("Please add your OpenAI API key to continue.", icon="🗝️")
else:
    # Create an OpenAI client.
    client = OpenAI(api_key=openai_api_key)

    # Initialize database and session state
    init_db()
    if "messages" not in st.session_state:
        msgs, tasks = load_history()
        st.session_state.messages = msgs
        st.session_state.admin_tasks = tasks

    # Sidebar admin controls
    with st.sidebar:
        if st.button("Reset conversation"):
            clear_history()
            st.experimental_rerun()
        st.download_button(
            "Export conversation",
            data=json.dumps(st.session_state.messages, indent=2),
            file_name="chat_history.json",
            mime="application/json",
        )

    # Display the existing chat messages via `st.chat_message`.
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Create a chat input field to allow the user to enter a message. This will display
    # automatically at the bottom of the page.
    if prompt := st.chat_input("What is up?"):

        # Store and display the current prompt.
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        save_message("user", prompt)

        # Prepare message history for the API call.
        history = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages
        ]

        try:
            # Ask the model for a response, allowing it to call tools.
            first_response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=history,
                tools=TOOLS,
            )

            message = first_response.choices[0].message

            if message.tool_calls:
                history.append(
                    {
                        "role": "assistant",
                        "content": message.content or "",
                        "tool_calls": [tc.model_dump() for tc in message.tool_calls],
                    }
                )

                for tool_call in message.tool_calls:
                    name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)
                    if name == "schedule_meeting":
                        result = schedule_meeting(**args)
                    elif name == "send_email":
                        result = send_email(**args)
                    elif name == "manage_todo":
                        result = manage_todo(**args)
                        # Refresh cached tasks after modification
                        _, st.session_state.admin_tasks = load_history()
                    else:
                        result = f"Function {name} not implemented."
                    history.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result,
                        }
                    )

                second_response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=history,
                )
                final_content = second_response.choices[0].message.content
            else:
                final_content = message.content

            with st.chat_message("assistant"):
                st.markdown(final_content)
            st.session_state.messages.append({"role": "assistant", "content": final_content})
            save_message("assistant", final_content)
        except openai.APIError as e:
            st.error(f"OpenAI API error: {e}")
            logger.exception("OpenAI API error during chat completion")
        except Exception:
            st.error("An unexpected error occurred. Please try again later.")
            logger.exception("Unexpected error during chat completion")
