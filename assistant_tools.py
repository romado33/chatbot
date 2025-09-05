from __future__ import annotations

"""Utility functions for handling assistant actions.

This module exposes simple helper functions that simulate common
actions an assistant might perform such as scheduling meetings,
 sending emails, or managing a to-do list.  These functions are
 designed to be used via OpenAI function calling from the Streamlit
 app.
"""

from pathlib import Path
import sqlite3
from typing import List

DB_PATH = Path("chat_history.db")


def schedule_meeting(topic: str, time: str) -> str:
    """Return a confirmation message for scheduling a meeting."""
    return f"Scheduled a meeting about '{topic}' at {time}."


def send_email(recipient: str, subject: str, body: str) -> str:
    """Return a confirmation message for sending an email."""
    return f"Email to {recipient} with subject '{subject}' has been sent."


def manage_todo(action: str, task: str | None = None) -> str:
    """Manage the to-do list stored in the database.

    Parameters
    ----------
    action:
        One of ``"add"``, ``"list"``, or ``"clear"``.
    task:
        The task description when ``action`` is ``"add"``.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if action == "add" and task:
        c.execute("INSERT INTO admin_tasks (task) VALUES (?)", (task,))
        conn.commit()
        conn.close()
        return f"Added task: {task}"
    if action == "list":
        c.execute("SELECT task FROM admin_tasks")
        tasks = [row[0] for row in c.fetchall()]
        conn.close()
        if tasks:
            return "Current tasks:\n" + "\n".join(f"- {t}" for t in tasks)
        return "No tasks in the list."
    if action == "clear":
        c.execute("DELETE FROM admin_tasks")
        conn.commit()
        conn.close()
        return "Cleared all tasks."

    conn.close()
    return "Unsupported action."

