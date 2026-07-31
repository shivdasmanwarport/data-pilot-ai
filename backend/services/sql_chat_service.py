import json
import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import text

from db import get_engine
from services.common import convert_numpy_types, sanitize_identifier


def normalize_llm_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text_value = item.get("text") or item.get("content")
                if text_value:
                    parts.append(str(text_value))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)
    return str(content)


def invoke_json_agent(llm, system_prompt: str, user_prompt_text: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
    if not llm:
        return fallback
    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt_text),
        ])
        raw_content = normalize_llm_content(response.content)
        match = re.search(r"\{.*\}", raw_content, re.DOTALL)
        if not match:
            return fallback
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else fallback
    except Exception as exc:
        print(f"Agent JSON parse error: {exc}")
        return fallback


def invoke_text_agent(llm, system_prompt: str, user_prompt_text: str) -> str:
    if not llm:
        return ""
    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt_text),
        ])
        return normalize_llm_content(response.content).strip()
    except Exception as exc:
        print(f"Agent text generation error: {exc}")
        return ""


def answer_from_table_context(question: str, table_context: Dict[str, Any]) -> Optional[str]:
    question_lower = question.lower()
    descriptions = table_context["column_descriptions"]

    if any(token in question_lower for token in ["how many rows", "row count", "number of rows", "total rows", "records"]):
        return f"The table '{table_context['table_name']}' has {table_context['row_count']:,} rows."

    if any(token in question_lower for token in ["what columns", "list columns", "show columns", "fields"]):
        lines = [f"Available columns in '{table_context['table_name']}':"]
        for column in table_context["columns"]:
            line = f"- {column['name']} ({column['type']})"
            if column["description"]:
                line += f": {column['description']}"
            lines.append(line)
        return "\n".join(lines)

    if any(token in question_lower for token in ["dataset prompt", "dataset context", "what is this dataset", "about this dataset"]):
        return table_context["prompt"] or "No dataset prompt was provided for this table."

    if "describe columns" in question_lower or "column descriptions" in question_lower:
        described_columns = [
            f"- {name}: {description}"
            for name, description in descriptions.items()
            if description
        ]
        return "\n".join(described_columns) if described_columns else "No column descriptions were provided for this table."

    return None


def validate_sql_query(sql: str, table_name: str) -> str:
    if not sql:
        raise ValueError("Empty SQL query")

    normalized_sql = sql.strip().rstrip(";")
    if ";" in normalized_sql:
        raise ValueError("Only one SQL statement is allowed")
    if not re.match(r"^(SELECT|WITH)\b", normalized_sql, re.IGNORECASE):
        raise ValueError("Only SELECT queries are allowed")
    if re.search(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|REPLACE|GRANT|REVOKE|MERGE|CALL|INTO\s+OUTFILE|LOAD_FILE)\b", normalized_sql, re.IGNORECASE):
        raise ValueError("Unsafe SQL operation detected")
    if table_name.lower() not in normalized_sql.lower():
        raise ValueError("The generated SQL does not reference the selected table")
    return normalized_sql


def is_numeric_type(type_name: str) -> bool:
    return any(token in type_name.lower() for token in ["int", "float", "double", "decimal", "numeric", "real"])


def find_column_from_question(question: str, table_context: Dict[str, Any], numeric_only: bool = False) -> Optional[Dict[str, Any]]:
    normalized_question = question.lower().replace("_", " ")
    for column in table_context["columns"]:
        if numeric_only and not is_numeric_type(column["type"]):
            continue
        candidates = {
            column["name"].lower(),
            column["name"].lower().replace("_", " "),
            column["name"].lower().replace("_", " ").rstrip("s"),
        }
        if any(candidate and candidate in normalized_question for candidate in candidates):
            return column
    return None


def generate_rule_based_sql(question: str, table_context: Dict[str, Any], history: List[Dict[str, Any]]) -> str:
    question_lower = question.lower()
    safe_table_name = sanitize_identifier(table_context["table_name"])

    if any(token in question_lower for token in ["they", "them", "that", "those", "same one", "same country", "same customer"]):
        for item in reversed(history):
            last_sql = item.get("sql_query")
            if last_sql:
                return last_sql

    if any(token in question_lower for token in ["show the first", "first 5 rows", "first few rows", "sample rows", "preview rows"]):
        return f"SELECT * FROM {safe_table_name} LIMIT 5"

    if any(token in question_lower for token in ["most", "highest", "top"]) and any(token in question_lower for token in ["which", "what"]):
        column = find_column_from_question(question, table_context)
        if column and not is_numeric_type(column["type"]):
            safe_column = sanitize_identifier(column["name"])
            return (
                f"SELECT {safe_column}, COUNT(*) AS record_count "
                f"FROM {safe_table_name} "
                f"GROUP BY {safe_column} "
                f"ORDER BY record_count DESC LIMIT 1"
            )

    numeric_column = find_column_from_question(question, table_context, numeric_only=True)
    if numeric_column:
        safe_column = sanitize_identifier(numeric_column["name"])
        if any(token in question_lower for token in ["average", "mean"]):
            return f"SELECT AVG({safe_column}) AS average_value FROM {safe_table_name}"
        if any(token in question_lower for token in ["sum", "total"]):
            return f"SELECT SUM({safe_column}) AS total_value FROM {safe_table_name}"
        if any(token in question_lower for token in ["max", "maximum", "highest"]):
            return f"SELECT MAX({safe_column}) AS max_value FROM {safe_table_name}"
        if any(token in question_lower for token in ["min", "minimum", "lowest"]):
            return f"SELECT MIN({safe_column}) AS min_value FROM {safe_table_name}"

    return ""


def execute_sql_query(sql: str) -> Dict[str, Any]:
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        rows = [convert_numpy_types(dict(row._mapping)) for row in result.fetchall()]
    return {
        "columns": list(rows[0].keys()) if rows else [],
        "rows": rows,
        "row_count": len(rows),
    }


def build_result_payload(query_result: Dict[str, Any], display_limit: int = 8) -> Optional[Dict[str, Any]]:
    if not query_result["rows"]:
        return None
    preview_rows = query_result["rows"][:display_limit]
    result_type = "table"
    if len(preview_rows) == 1 and len(preview_rows[0]) == 1:
        result_type = "scalar"
    return {
        "type": result_type,
        "columns": query_result["columns"],
        "rows": preview_rows,
        "row_count": query_result["row_count"],
        "truncated": query_result["row_count"] > display_limit,
    }


def format_query_results(query_result: Dict[str, Any], result_payload: Optional[Dict[str, Any]]) -> str:
    if not query_result["rows"]:
        return "No matching rows found."

    if result_payload and result_payload["type"] == "scalar":
        first_row = result_payload["rows"][0]
        key = next(iter(first_row))
        return f"{key.replace('_', ' ').title()}: **{first_row[key]}**"

    row_count = query_result["row_count"]
    if result_payload and result_payload["truncated"]:
        return f"Returned **{row_count}** rows. A preview is shown below."
    return f"Returned **{row_count}** rows. Review the result table below."


def generate_sql_with_agents(llm, question: str, table_context: Dict[str, Any], history: List[Dict[str, Any]]) -> str:
    planner_fallback = {
        "can_answer": True,
        "needs_sql": True,
        "question_type": "analysis",
        "relevant_columns": [],
        "analysis": "Use SQL against the selected table.",
    }
    planner_prompt = """You are the planning agent in a multi-agent SQL analytics system.
Return JSON only with these keys:
can_answer: boolean
needs_sql: boolean
question_type: string
relevant_columns: string array
analysis: string

Rules:
- Only the selected table is available.
- Do not invent columns.
- Set needs_sql to false for pure schema or prompt questions.
- Use the recent chat history, including prior SQL when present, to resolve follow-up questions.
"""
    planner_input = json.dumps(
        {"question": question, "table_context": table_context, "history": history[-5:]},
        default=str,
        indent=2,
    )
    plan = invoke_json_agent(llm, planner_prompt, planner_input, planner_fallback)

    if not plan.get("can_answer", True) or not plan.get("needs_sql", True):
        return ""

    sql_fallback = {
        "sql": f"SELECT * FROM {sanitize_identifier(table_context['table_name'])} LIMIT 10",
        "notes": "Fallback preview query",
    }
    sql_prompt = """You are the SQL generation agent in a multi-agent analytics system.
Return JSON only with these keys:
sql: string
notes: string

Rules:
- Output one read-only MySQL query.
- Use only SELECT or WITH.
- Use only the selected table and the provided columns.
- For row-level results, include LIMIT 50 or less.
- Use aggregation for count, average, max, min, totals, ranking, and comparison questions.
- Use recent chat history to resolve references like "that result", "those rows", or "same country".
"""
    sql_input = json.dumps(
        {"question": question, "plan": plan, "table_context": table_context, "history": history[-5:]},
        default=str,
        indent=2,
    )
    sql_payload = invoke_json_agent(llm, sql_prompt, sql_input, sql_fallback)
    return sql_payload.get("sql", "").strip()


def repair_sql_with_agent(llm, question: str, table_context: Dict[str, Any], sql: str, error_message: str) -> str:
    repair_fallback = {"sql": "", "notes": ""}
    repair_prompt = """You are the SQL repair agent in a multi-agent analytics system.
Return JSON only with these keys:
sql: string
notes: string

Rules:
- Fix the SQL so it runs on MySQL.
- Keep it read-only and limited to the selected table.
- Output a single SELECT or WITH query.
"""
    repair_input = json.dumps(
        {
            "question": question,
            "table_context": table_context,
            "broken_sql": sql,
            "database_error": error_message,
        },
        default=str,
        indent=2,
    )
    repaired = invoke_json_agent(llm, repair_prompt, repair_input, repair_fallback)
    return repaired.get("sql", "").strip()


def summarize_sql_result(
    llm,
    question: str,
    table_context: Dict[str, Any],
    sql: str,
    query_result: Dict[str, Any],
    result_payload: Optional[Dict[str, Any]],
) -> str:
    if not query_result["rows"]:
        return "No matching rows found for that question."

    summary_prompt = """You are the answer agent in a multi-agent SQL chatbot.
Answer the user's question using the executed SQL result.
Rules:
- Be concise and factual.
- If the result is tabular, summarize the key rows clearly.
- Do not invent values that are not present in the result.
- Mention when a preview table is shown.
"""
    summary_input = json.dumps(
        {
            "question": question,
            "table_context": {
                "table_name": table_context["table_name"],
                "prompt": table_context["prompt"],
                "column_descriptions": table_context["column_descriptions"],
            },
            "sql": sql,
            "query_result": {
                "row_count": query_result["row_count"],
                "rows": query_result["rows"][:25],
            },
        },
        default=str,
        indent=2,
    )
    answer = invoke_text_agent(llm, summary_prompt, summary_input)
    return answer or format_query_results(query_result, result_payload)


def answer_question_with_sql_agents(llm, question: str, table_context: Dict[str, Any], history: List[Dict[str, Any]]) -> Dict[str, Optional[Any]]:
    context_answer = answer_from_table_context(question, table_context)
    if context_answer:
        return {"answer": context_answer, "sql_query": None, "result_payload": None}

    sql = generate_rule_based_sql(question, table_context, history)
    if not sql:
        sql = generate_sql_with_agents(llm, question, table_context, history)
    if not sql:
        return {"answer": "", "sql_query": None, "result_payload": None}

    try:
        validated_sql = validate_sql_query(sql, table_context["table_name"])
        query_result = execute_sql_query(validated_sql)
    except Exception as exc:
        repaired_sql = repair_sql_with_agent(llm, question, table_context, sql, str(exc))
        if not repaired_sql:
            print(f"SQL generation error: {exc}")
            return {"answer": "", "sql_query": None, "result_payload": None}
        try:
            validated_sql = validate_sql_query(repaired_sql, table_context["table_name"])
            query_result = execute_sql_query(validated_sql)
        except Exception as repair_exc:
            print(f"SQL repair error: {repair_exc}")
            return {"answer": "", "sql_query": None, "result_payload": None}

    result_payload = build_result_payload(query_result)
    return {
        "answer": summarize_sql_result(llm, question, table_context, validated_sql, query_result, result_payload),
        "sql_query": validated_sql,
        "result_payload": result_payload,
    }