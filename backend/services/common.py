import re
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

import numpy as np
import pandas as pd


def convert_numpy_types(obj: Any):
    if isinstance(obj, (np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    if isinstance(obj, (np.float64, np.float32, np.float16)):
        return float(obj)
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, pd.Series):
        return obj.tolist()
    if isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    return obj


def sanitize_identifier(identifier: str) -> str:
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", identifier):
        raise ValueError(f"Invalid SQL identifier: {identifier}")
    return f"`{identifier}`"


def humanize_identifier(identifier: str) -> str:
    compact = re.sub(r"[_\s]+", " ", identifier).strip()
    return compact.title() if compact else "Dataset"


def build_session_title(question: Optional[str], table_name: str, explicit_title: Optional[str] = None) -> str:
    if explicit_title and explicit_title.strip():
        return explicit_title.strip()[:80]

    if question:
        normalized = re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9\s]", "", question)).strip()
        if normalized:
            words = normalized.split()
            return " ".join(words[:8])[:80]

    return f"{humanize_identifier(table_name)} Overview"


def should_auto_rename_session(current_title: str, table_name: str) -> bool:
    normalized = (current_title or "").strip().lower()
    defaults = {
        build_session_title(None, table_name).lower(),
        f"{table_name.lower()} session",
    }
    return not normalized or normalized in defaults or normalized.endswith(" session") or normalized.endswith(" overview")