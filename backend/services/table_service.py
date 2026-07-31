import re
from io import BytesIO
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import HTTPException
from sqlalchemy import inspect, text

from db import get_engine
from services.common import convert_numpy_types, sanitize_identifier
from services.session_service import get_sessions_for_user


def get_all_tables() -> List[str]:
    engine = get_engine()
    inspector = inspect(engine)
    all_tables = inspector.get_table_names()
    internal_tables = {"chat_history", "chat_sessions", "app_users"}
    return [
        table_name
        for table_name in all_tables
        if not table_name.endswith("_metadata") and not table_name.endswith("_prompt") and table_name not in internal_tables
    ]


def get_table_names_with_sessions(user_id: int) -> List[str]:
    sessions = get_sessions_for_user(user_id)
    valid_tables = set(get_all_tables())
    ordered_names: List[str] = []
    for session in sessions:
        table_name = session["table_name"]
        if table_name in valid_tables and table_name not in ordered_names:
            ordered_names.append(table_name)
    for table_name in valid_tables:
        if table_name not in ordered_names:
            ordered_names.append(table_name)
    return ordered_names


def get_table_context(table_name: str, sample_size: int = 5) -> Dict[str, Any]:
    engine = get_engine()
    inspector = inspect(engine)

    if table_name not in inspector.get_table_names():
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

    safe_table_name = sanitize_identifier(table_name)
    metadata_table_name = f"{table_name}_metadata"
    prompt_table_name = f"{table_name}_prompt"
    descriptions: Dict[str, str] = {}
    prompt_text = None

    if metadata_table_name in inspector.get_table_names():
        safe_metadata_table = sanitize_identifier(metadata_table_name)
        with engine.connect() as conn:
            metadata_rows = conn.execute(
                text(f"SELECT column_name, description FROM {safe_metadata_table}")
            ).fetchall()
        descriptions = {row[0]: row[1] for row in metadata_rows if row[1]}

    if prompt_table_name in inspector.get_table_names():
        safe_prompt_table = sanitize_identifier(prompt_table_name)
        with engine.connect() as conn:
            prompt_row = conn.execute(
                text(f"SELECT prompt FROM {safe_prompt_table} LIMIT 1")
            ).fetchone()
        prompt_text = prompt_row[0] if prompt_row else None

    columns = inspector.get_columns(table_name)
    with engine.connect() as conn:
        row_count = conn.execute(
            text(f"SELECT COUNT(*) AS total_rows FROM {safe_table_name}")
        ).scalar() or 0
        sample_rows_result = conn.execute(
            text(f"SELECT * FROM {safe_table_name} LIMIT {sample_size}")
        )
        sample_rows = [convert_numpy_types(dict(row._mapping)) for row in sample_rows_result.fetchall()]

    return {
        "table_name": table_name,
        "row_count": int(row_count),
        "prompt": prompt_text,
        "column_descriptions": descriptions,
        "columns": [
            {
                "name": column["name"],
                "type": str(column["type"]),
                "description": descriptions.get(column["name"], ""),
            }
            for column in columns
        ],
        "sample_rows": sample_rows,
    }


def load_dataframe_for_table(table_name: str) -> pd.DataFrame:
    return pd.read_sql_table(table_name, get_engine())


def prepare_uploaded_file(file_bytes: bytes, table_name: str) -> Dict[str, Any]:
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table_name):
        raise HTTPException(status_code=400, detail="Invalid table name")

    df = pd.read_csv(BytesIO(file_bytes))
    if df.empty:
        raise HTTPException(status_code=400, detail="CSV file is empty")

    original_columns = df.columns.tolist()
    df.columns = [re.sub(r"[^a-zA-Z0-9_]", "_", column) for column in df.columns]
    column_info = []
    for column_name in df.columns:
        column_info.append(
            {
                "name": column_name,
                "original_name": original_columns[df.columns.tolist().index(column_name)],
                "type": str(df[column_name].dtype),
                "sample_values": convert_numpy_types(df[column_name].dropna().head(3).tolist()),
                "null_count": int(df[column_name].isnull().sum()),
                "unique_count": int(df[column_name].nunique()),
                "description": "",
            }
        )

    return {
        "dataframe": df,
        "columns": df.columns.tolist(),
        "column_info": column_info,
        "preview": convert_numpy_types(df.head(5).fillna("").to_dict(orient="records")),
        "row_count": int(len(df)),
        "table_name": table_name,
    }


def persist_table_with_metadata(
    dataframe: pd.DataFrame,
    table_name: str,
    column_descriptions: Dict[str, str],
    prompt: Optional[str],
) -> Dict[str, Any]:
    engine = get_engine()
    dataframe.to_sql(name=table_name, con=engine, if_exists="replace", index=False, chunksize=10000)

    metadata_table_name = f"{table_name}_metadata"
    prompt_table_name = f"{table_name}_prompt"

    with engine.connect() as conn:
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {metadata_table_name} (
                id INT AUTO_INCREMENT PRIMARY KEY,
                table_name VARCHAR(255),
                column_name VARCHAR(255),
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_column (table_name, column_name)
            )
        """))

        for column_name, description in column_descriptions.items():
            if description:
                conn.execute(
                    text(f"""
                        INSERT INTO {metadata_table_name} (table_name, column_name, description)
                        VALUES (:table_name, :column_name, :description)
                        ON DUPLICATE KEY UPDATE description = :description
                    """),
                    {"table_name": table_name, "column_name": column_name, "description": description},
                )

        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {prompt_table_name} (
                id INT AUTO_INCREMENT PRIMARY KEY,
                table_name VARCHAR(255) UNIQUE,
                prompt TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """))

        if prompt:
            conn.execute(
                text(f"""
                    INSERT INTO {prompt_table_name} (table_name, prompt)
                    VALUES (:table_name, :prompt)
                    ON DUPLICATE KEY UPDATE prompt = :prompt, updated_at = CURRENT_TIMESTAMP
                """),
                {"table_name": table_name, "prompt": prompt},
            )

        conn.commit()

    return {
        "success": True,
        "message": f"Table '{table_name}' created successfully!",
        "table_name": table_name,
        "row_count": int(len(dataframe)),
        "column_count": int(len(dataframe.columns)),
        "column_descriptions": column_descriptions,
        "prompt": prompt,
    }