import json
import os
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from db import get_engine
from services.common import build_session_title, convert_numpy_types, should_auto_rename_session


DEFAULT_USER = {
    "display_name": os.getenv("APP_DEFAULT_USER_NAME", "Data Analyst"),
    "email": os.getenv("APP_DEFAULT_USER_EMAIL", "analyst@datapilot.local"),
    "avatar_initials": os.getenv("APP_DEFAULT_USER_INITIALS", "DA"),
}


def ensure_user_schema(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS app_users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            display_name VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            avatar_initials VARCHAR(8) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))


def ensure_chat_session_schema(conn):
    ensure_user_schema(conn)
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            table_name VARCHAR(255) NOT NULL,
            title VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """))


def ensure_chat_history_schema(conn):
    ensure_user_schema(conn)
    ensure_chat_session_schema(conn)
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            session_id INT NULL,
            user_id INT NULL,
            table_name VARCHAR(255) NOT NULL,
            user_message TEXT NOT NULL,
            assistant_response TEXT,
            sql_query TEXT,
            result_payload LONGTEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    for column_name, ddl in {
        "sql_query": "ALTER TABLE chat_history ADD COLUMN sql_query TEXT NULL AFTER assistant_response",
        "result_payload": "ALTER TABLE chat_history ADD COLUMN result_payload LONGTEXT NULL AFTER sql_query",
        "session_id": "ALTER TABLE chat_history ADD COLUMN session_id INT NULL AFTER id",
        "user_id": "ALTER TABLE chat_history ADD COLUMN user_id INT NULL AFTER session_id",
    }.items():
        has_column = conn.execute(text(f"SHOW COLUMNS FROM chat_history LIKE '{column_name}'")).fetchone()
        if not has_column:
            conn.execute(text(ddl))


def ensure_default_user(conn) -> Dict[str, Any]:
    ensure_user_schema(conn)
    existing_user = conn.execute(
        text("SELECT id, display_name, email, avatar_initials FROM app_users WHERE email = :email LIMIT 1"),
        {"email": DEFAULT_USER["email"]},
    ).mappings().fetchone()
    if existing_user:
        return dict(existing_user)

    conn.execute(
        text("INSERT INTO app_users (display_name, email, avatar_initials) VALUES (:display_name, :email, :avatar_initials)"),
        DEFAULT_USER,
    )
    created_user = conn.execute(
        text("SELECT id, display_name, email, avatar_initials FROM app_users WHERE email = :email LIMIT 1"),
        {"email": DEFAULT_USER["email"]},
    ).mappings().fetchone()
    return dict(created_user)


def get_default_user() -> Dict[str, Any]:
    engine = get_engine()
    with engine.connect() as conn:
        user = ensure_default_user(conn)
        conn.commit()
    return user


def resolve_user_id(explicit_user_id: Optional[int] = None) -> int:
    if explicit_user_id:
        return explicit_user_id
    return int(get_default_user()["id"])


def create_chat_session(table_name: str, user_id: int, title: Optional[str] = None, seed_question: Optional[str] = None) -> Dict[str, Any]:
    engine = get_engine()
    session_title = build_session_title(seed_question, table_name, title)
    with engine.connect() as conn:
        ensure_chat_session_schema(conn)
        conn.execute(
            text("INSERT INTO chat_sessions (user_id, table_name, title) VALUES (:user_id, :table_name, :title)"),
            {"user_id": user_id, "table_name": table_name, "title": session_title},
        )
        created = conn.execute(
            text("SELECT id, user_id, table_name, title, created_at, updated_at FROM chat_sessions WHERE user_id = :user_id AND table_name = :table_name ORDER BY id DESC LIMIT 1"),
            {"user_id": user_id, "table_name": table_name},
        ).mappings().fetchone()
        conn.commit()
    return convert_numpy_types(dict(created))


def get_chat_session(session_id: int) -> Optional[Dict[str, Any]]:
    engine = get_engine()
    with engine.connect() as conn:
        ensure_chat_session_schema(conn)
        session_row = conn.execute(
            text("SELECT id, user_id, table_name, title, created_at, updated_at FROM chat_sessions WHERE id = :session_id LIMIT 1"),
            {"session_id": session_id},
        ).mappings().fetchone()
    return convert_numpy_types(dict(session_row)) if session_row else None


def update_chat_session_timestamp(conn, session_id: int):
    conn.execute(
        text("UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = :session_id"),
        {"session_id": session_id},
    )


def maybe_name_session_from_question(conn, session_id: int, current_title: str, question: str, table_name: str):
    if not should_auto_rename_session(current_title, table_name):
        return
    proposed_title = build_session_title(question, table_name)
    conn.execute(
        text("UPDATE chat_sessions SET title = :title WHERE id = :session_id"),
        {"title": proposed_title, "session_id": session_id},
    )


def save_chat_history(
    table_name: str,
    user_message: str,
    assistant_response: str,
    sql_query: Optional[str] = None,
    session_id: Optional[int] = None,
    user_id: Optional[int] = None,
    result_payload: Optional[Dict[str, Any]] = None,
):
    engine = get_engine()
    with engine.connect() as conn:
        ensure_chat_history_schema(conn)
        if user_id is None:
            user_id = ensure_default_user(conn)["id"]
        conn.execute(
            text("""
                INSERT INTO chat_history (
                    session_id, user_id, table_name, user_message, assistant_response, sql_query, result_payload
                ) VALUES (
                    :session_id, :user_id, :table_name, :user_message, :assistant_response, :sql_query, :result_payload
                )
            """),
            {
                "session_id": session_id,
                "user_id": user_id,
                "table_name": table_name,
                "user_message": user_message,
                "assistant_response": assistant_response,
                "sql_query": sql_query,
                "result_payload": json.dumps(result_payload) if result_payload else None,
            },
        )
        if session_id:
            session_row = conn.execute(
                text("SELECT title FROM chat_sessions WHERE id = :session_id LIMIT 1"),
                {"session_id": session_id},
            ).fetchone()
            if session_row:
                maybe_name_session_from_question(conn, session_id, session_row[0], user_message, table_name)
                update_chat_session_timestamp(conn, session_id)
        conn.commit()


def get_chat_history(table_name: Optional[str] = None, limit: int = 10, session_id: Optional[int] = None) -> List[Dict[str, Any]]:
    engine = get_engine()
    with engine.connect() as conn:
        ensure_chat_history_schema(conn)
        if session_id is not None:
            result = conn.execute(
                text("""
                    SELECT session_id, user_id, user_message, assistant_response, sql_query, result_payload, timestamp
                    FROM chat_history WHERE session_id = :session_id ORDER BY id ASC LIMIT :limit
                """),
                {"session_id": session_id, "limit": limit},
            )
        else:
            result = conn.execute(
                text("""
                    SELECT session_id, user_id, user_message, assistant_response, sql_query, result_payload, timestamp
                    FROM chat_history WHERE table_name = :table_name ORDER BY id DESC LIMIT :limit
                """),
                {"table_name": table_name, "limit": limit},
            )
        rows = result.fetchall()

    history = []
    iterable_rows = rows if session_id is not None else reversed(rows)
    for row in iterable_rows:
        result_payload = json.loads(row[5]) if row[5] else None
        history.append(
            {
                "session_id": row[0],
                "user_id": row[1],
                "user_message": row[2],
                "assistant_response": row[3],
                "sql_query": row[4],
                "result_payload": result_payload,
                "timestamp": convert_numpy_types(row[6]),
            }
        )
    return history


def get_sessions_for_user(user_id: int, table_name: Optional[str] = None) -> List[Dict[str, Any]]:
    engine = get_engine()
    with engine.connect() as conn:
        ensure_chat_session_schema(conn)
        ensure_chat_history_schema(conn)
        base_sql = """
            SELECT cs.id, cs.user_id, cs.table_name, cs.title, cs.created_at, cs.updated_at,
                   COUNT(ch.id) AS message_count,
                   MAX(ch.timestamp) AS last_message_at
            FROM chat_sessions cs
            LEFT JOIN chat_history ch ON ch.session_id = cs.id
            WHERE cs.user_id = :user_id
        """
        params: Dict[str, Any] = {"user_id": user_id}
        if table_name:
            base_sql += " AND cs.table_name = :table_name"
            params["table_name"] = table_name
        base_sql += " GROUP BY cs.id, cs.user_id, cs.table_name, cs.title, cs.created_at, cs.updated_at ORDER BY COALESCE(MAX(ch.timestamp), cs.updated_at) DESC"
        rows = conn.execute(text(base_sql), params).mappings().fetchall()
    return [convert_numpy_types(dict(row)) for row in rows]