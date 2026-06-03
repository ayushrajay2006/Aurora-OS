import os
import sqlite3
import json
import time
from typing import List, Dict, Any, Optional
from config.config import config
from config.logging import logger

class Memory:
    def __init__(self):
        self.db_path = config.db_path
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Returns a sqlite3 connection. Opens a new connection to ensure thread safety."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes tables if they do not exist."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 1. Chat conversation history table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS conversation (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        timestamp TEXT NOT NULL
                    )
                """)
                
                # 2. Key-value table for long term memory / facts
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS long_term_memory (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        timestamp TEXT NOT NULL
                    )
                """)
                
                # 3. Action / tool execution history
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS action_history (
                        id TEXT PRIMARY KEY,
                        tool_name TEXT NOT NULL,
                        args TEXT NOT NULL,
                        status TEXT NOT NULL,
                        result TEXT,
                        timestamp TEXT NOT NULL
                    )
                """)
                
                conn.commit()
            logger.debug("Database initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize SQLite database: {e}")

    # Conversation History API
    def save_message(self, role: str, content: str):
        """Saves a conversation message in the database."""
        try:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT INTO conversation (role, content, timestamp) VALUES (?, ?, ?)",
                    (role, content, timestamp)
                )
                conn.commit()
            logger.debug(f"Saved message from {role} in database.")
        except Exception as e:
            logger.error(f"Error saving message: {e}")

    def load_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Loads conversation history up to the limit."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT role, content, timestamp FROM (SELECT id, role, content, timestamp FROM conversation ORDER BY id DESC LIMIT ?) ORDER BY id ASC",
                    (limit,)
                )
                rows = cursor.fetchall()
                return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in rows]
        except Exception as e:
            logger.error(f"Error loading conversation history: {e}")
            return []

    def clear_history(self):
        """Clears all conversation history."""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM conversation")
                conn.commit()
            logger.info("Conversation history cleared from database.")
        except Exception as e:
            logger.error(f"Error clearing conversation history: {e}")

    # Long-term Memory facts API
    def set_fact(self, key: str, value: str):
        """Sets a key-value pair in long-term memory."""
        try:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO long_term_memory (key, value, timestamp) VALUES (?, ?, ?)",
                    (key, value, timestamp)
                )
                conn.commit()
            logger.info(f"Memory updated: {key} = {value}")
        except Exception as e:
            logger.error(f"Error setting memory key '{key}': {e}")

    def get_fact(self, key: str) -> Optional[str]:
        """Gets a value by key from long-term memory."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM long_term_memory WHERE key = ?", (key,))
                row = cursor.fetchone()
                return row["value"] if row else None
        except Exception as e:
            logger.error(f"Error getting memory key '{key}': {e}")
            return None

    def delete_fact(self, key: str):
        """Deletes a key-value pair from long-term memory."""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM long_term_memory WHERE key = ?", (key,))
                conn.commit()
            logger.info(f"Memory key deleted: {key}")
        except Exception as e:
            logger.error(f"Error deleting memory key '{key}': {e}")

    def get_all_facts(self) -> Dict[str, str]:
        """Returns all long-term memory facts as a dictionary."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT key, value FROM long_term_memory")
                rows = cursor.fetchall()
                return {row["key"]: row["value"] for row in rows}
        except Exception as e:
            logger.error(f"Error retrieving all memory facts: {e}")
            return {}

    # Action / Tool Logging API
    def log_action(self, action_id: str, tool_name: str, args: Dict[str, Any], status: str):
        """Logs an action execution request."""
        try:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            args_str = json.dumps(args)
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO action_history (id, tool_name, args, status, timestamp) VALUES (?, ?, ?, ?, ?)",
                    (action_id, tool_name, args_str, status, timestamp)
                )
                conn.commit()
            logger.debug(f"Action logged: {action_id} - {tool_name} [{status}]")
        except Exception as e:
            logger.error(f"Error logging action {action_id}: {e}")

    def update_action(self, action_id: str, status: str, result: Any):
        """Updates the status and results of a logged action."""
        try:
            result_str = json.dumps(result) if result is not None else None
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE action_history SET status = ?, result = ? WHERE id = ?",
                    (status, result_str, action_id)
                )
                conn.commit()
            logger.debug(f"Action updated: {action_id} -> status: {status}")
        except Exception as e:
            logger.error(f"Error updating action {action_id}: {e}")

# Global memory instance
memory = Memory()
