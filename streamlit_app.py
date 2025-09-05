import json
import sqlite3
import logging
import os
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


def handle_explicit_command(prompt: str) -> str | None:
    """Execute assistant tools when the user issues a slash command.

    Commands
    --------
    /schedule <topic>|<time>
        Schedule a meeting.
    /email <recipient>|<subject>|<body>
        Send a mock email.
    /todo add <task> | /todo list | /todo clear
        Manage to-do items.
    """

    if prompt.startswith("/schedule"):
        try:
            _, rest = prompt.split(" ", 1)
            topic, time = [s.strip() for s in rest.split("|", 1)]
        except ValueError:
            return "Usage: /schedule <topic>|<time>"
        return schedule_meeting(topic=topic, time=time)

    if prompt.startswith("/email"):
        try:
            _, rest = prompt.split(" ", 1)
            recipient, subject, body = [s.strip() for s in rest.split("|", 2)]
        except ValueError:
            return "Usage: /email <recipient>|<subject>|<body>"
        return send_email(recipient=recipient, subject=subject, body=body)

    if prompt.startswith("/todo"):
        parts = prompt.split(" ", 2)
        if len(parts) < 2:
            return "Usage: /todo add <task> | /todo list | /todo clear"
        action = parts[1]
        if action == "add" and len(parts) == 3:
            result = manage_todo("add", task=parts[2].strip())
            # refresh cache
            _, st.session_state.admin_tasks = load_history()
            return result
        if action in {"list", "clear"}:
            result = manage_todo(action)
            if action != "list":
                _, st.session_state.admin_tasks = load_history()
            return result
        return "Usage: /todo add <task> | /todo list | /todo clear"

    return None


# Retrieve OpenAI API key from Streamlit secrets or environment variables.
openai_api_key = st.secrets.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")

# If no key is found, ask the user for it via `st.text_input`.
if not openai_api_key:
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

        # Check for explicit slash commands before calling the model.
        if command_response := handle_explicit_command(prompt):
            with st.chat_message("assistant"):
                st.markdown(command_response)
            st.session_state.messages.append({"role": "assistant", "content": command_response})
            save_message("assistant", command_response)
        else:
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
            except openai.APIError as e:
                st.error(f"OpenAI API error: {e}")
                logger.exception("OpenAI API error during chat completion")
            except Exception:
                st.error("An unexpected error occurred. Please try again later.")
                logger.exception("Unexpected error during chat completion")
            else:
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

                try:
                    stream = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=history,
                        stream=True,
                    )
                    with st.chat_message("assistant"):
                        final_content = st.write_stream(
                            chunk.choices[0].delta.content or "" for chunk in stream
                        )
                    st.session_state.messages.append(
                        {"role": "assistant", "content": final_content}
                    )
                    save_message("assistant", final_content)
                except openai.APIError as e:
                    st.error(f"OpenAI API error: {e}")
                    logger.exception("OpenAI API error during response streaming")
                except Exception:
                    st.error("An unexpected error occurred. Please try again later.")
                    logger.exception("Unexpected error during response streaming")
