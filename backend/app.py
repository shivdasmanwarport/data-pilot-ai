from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os
from dotenv import load_dotenv
from model import ChatRequest, TableCreationRequest, ColumnDescription, SelectTableRequest, SessionCreateRequest, SessionSelectRequest
from typing import Any, Dict, Optional

# LangChain imports – updated for newer versions
from langchain_groq import ChatGroq
from db import get_engine
from services.session_service import (
    get_default_user,
    resolve_user_id,
    create_chat_session,
    get_chat_session,
    get_chat_history,
    get_sessions_for_user,
    save_chat_history,
)
from services.sql_chat_service import answer_question_with_sql_agents
from services.table_service import (
    get_all_tables,
    get_table_context,
    get_table_names_with_sessions,
    load_dataframe_for_table,
    prepare_uploaded_file,
    persist_table_with_metadata,
)

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://localhost:4201", "http://127.0.0.1:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Groq Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
USE_LLM = os.getenv("USE_LLM", "true").lower() == "true"
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
LLM_ENABLED = USE_LLM and bool(GROQ_API_KEY)

# Initialize Groq LLM for LangChain
llm = None
llm_init_error = None
if LLM_ENABLED:
    try:
        llm = ChatGroq(
            groq_api_key=GROQ_API_KEY,
            model_name=GROQ_MODEL,
            temperature=0.7
        )
        print(f"✅ LangChain Groq LLM initialized with model: {GROQ_MODEL}")
    except Exception as e:
        llm_init_error = str(e)
        LLM_ENABLED = False
        print(f"❌ Failed to initialize Groq LLM: {e}")
elif USE_LLM and not GROQ_API_KEY:
    print("ℹ️ LangChain Groq LLM disabled because GROQ_API_KEY is not set")

# Global state
uploaded_df = None
current_table_name = None
current_columns = []
column_descriptions = {}
user_prompt = None
current_session_id = None

def sync_active_table_state(table_context: Dict[str, Any], dataframe: Optional[pd.DataFrame] = None):
    global uploaded_df, current_table_name, current_columns, column_descriptions, user_prompt

    current_table_name = table_context["table_name"]
    current_columns = [column["name"] for column in table_context["columns"]]
    column_descriptions = table_context["column_descriptions"]
    user_prompt = table_context["prompt"]

    if dataframe is not None:
        uploaded_df = dataframe

# ---------- Endpoints ----------
@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    table_name: str = Query(..., description="Name of the table to create")
):
    global uploaded_df, current_table_name, current_columns, column_descriptions, user_prompt
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    try:
        upload_payload = prepare_uploaded_file(await file.read(), table_name)
        uploaded_df = upload_payload["dataframe"]
        current_table_name = table_name
        current_columns = upload_payload["columns"]
        column_descriptions = {}
        user_prompt = None

        return {
            "success": True,
            "message": f"Successfully uploaded {upload_payload['row_count']} rows from '{file.filename}'",
            "columns": current_columns,
            "column_info": upload_payload["column_info"],
            "preview": upload_payload["preview"],
            "row_count": upload_payload["row_count"],
            "table_name": table_name,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@app.post("/create-table")
async def create_table_with_metadata(request: TableCreationRequest = Body(...)):
    global uploaded_df, current_table_name, current_columns, column_descriptions, user_prompt
    
    if uploaded_df is None:
        raise HTTPException(status_code=400, detail="No data uploaded. Please upload a CSV file first.")
    
    try:
        column_descriptions = {}
        for col_desc in request.column_descriptions:
            column_descriptions[col_desc.column_name] = col_desc.description
        
        user_prompt = request.prompt
        return persist_table_with_metadata(uploaded_df, current_table_name, column_descriptions, user_prompt)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating table: {str(e)}")

@app.post("/table/select")
async def select_table(request: SelectTableRequest):
    table_name = request.table_name
    
    try:
        table_context = get_table_context(table_name)
        df = load_dataframe_for_table(table_name)
        sync_active_table_state(table_context, df)
        
        return {
            "success": True,
            "message": f"Table '{table_name}' selected",
            "table_name": table_name,
            "columns": current_columns,
            "row_count": len(df),
            "column_descriptions": column_descriptions,
            "prompt": user_prompt
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading table: {str(e)}")

@app.get("/me")
async def get_current_user():
    try:
        return get_default_user()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading user: {str(e)}")

@app.get("/sessions")
async def list_sessions(table_name: Optional[str] = None, user_id: Optional[int] = None):
    try:
        resolved_user_id = resolve_user_id(user_id)
        sessions = get_sessions_for_user(resolved_user_id, table_name)
        return {"sessions": sessions, "count": len(sessions)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing sessions: {str(e)}")

@app.post("/sessions")
async def create_session(request: SessionCreateRequest):
    try:
        resolved_user_id = resolve_user_id(request.user_id)
        session_record = create_chat_session(request.table_name, resolved_user_id, request.title, None)
        return session_record
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating session: {str(e)}")

@app.post("/sessions/select")
async def select_session(request: SessionSelectRequest):
    global current_session_id
    try:
        session_record = get_chat_session(request.session_id)
        if not session_record:
            raise HTTPException(status_code=404, detail="Session not found")
        table_context = get_table_context(session_record["table_name"])
        sync_active_table_state(table_context)
        current_session_id = session_record["id"]
        return {
            "session": session_record,
            "table": {
                "table_name": table_context["table_name"],
                "columns": [column["name"] for column in table_context["columns"]],
                "row_count": table_context["row_count"],
                "prompt": table_context["prompt"]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error selecting session: {str(e)}")

@app.get("/tables")
async def list_tables(user_id: Optional[int] = None):
    try:
        resolved_user_id = resolve_user_id(user_id)
        tables = get_table_names_with_sessions(resolved_user_id)
        return {"tables": tables, "count": len(tables)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing tables: {str(e)}")

@app.get("/history")
async def get_history(table_name: Optional[str] = None, session_id: Optional[int] = None):
    try:
        if session_id is None and not table_name:
            raise HTTPException(status_code=400, detail="session_id or table_name is required")
        history = get_chat_history(table_name=table_name, session_id=session_id)
        return {"history": history}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching history: {str(e)}")

@app.post("/chat")
async def chat(request: ChatRequest):
    global uploaded_df, current_session_id

    question = request.question.strip()
    target_table_name = request.table_name or current_table_name
    resolved_user_id = resolve_user_id(request.user_id)
    target_session_id = request.session_id or current_session_id

    if not question:
        raise HTTPException(status_code=400, detail="Question is required")

    if not target_table_name:
        return {
            "answer": "No dataset loaded. Please create or select a table first."
        }

    try:
        if target_session_id:
            session_record = get_chat_session(target_session_id)
            if not session_record:
                raise HTTPException(status_code=404, detail="Session not found")
            target_table_name = session_record["table_name"]
        elif target_table_name:
            session_record = create_chat_session(target_table_name, resolved_user_id, None, question)
            target_session_id = int(session_record["id"])
        else:
            session_record = None

        table_context = get_table_context(target_table_name)
        sync_active_table_state(table_context)
        current_session_id = target_session_id
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error loading table context: {str(exc)}")

    history = get_chat_history(table_name=target_table_name, limit=20, session_id=target_session_id)
    agent_result = answer_question_with_sql_agents(llm, question, table_context, history)
    answer = agent_result["answer"]
    sql_query = agent_result["sql_query"]
    result_payload = agent_result.get("result_payload")

    if not answer:
        if uploaded_df is None or current_table_name != target_table_name:
            uploaded_df = load_dataframe_for_table(target_table_name)
        answer = process_question_with_metadata(
            question.lower(),
            uploaded_df,
            target_table_name,
            table_context["column_descriptions"],
            table_context["prompt"]
        )
        sql_query = None
        result_payload = None

    save_chat_history(target_table_name, question, answer, sql_query, target_session_id, resolved_user_id, result_payload)
    
    return {"answer": answer, "sql_query": sql_query, "session_id": target_session_id, "result_payload": result_payload}

# ---------- Rule-based fallback ----------
def process_question_with_metadata(question: str, df: pd.DataFrame, table_name: str, descriptions: Dict, prompt: Optional[str]) -> str:
    question_lower = question.lower()
    context = ""
    if prompt:
        context += f"Context about the dataset: {prompt}\n\n"
    
    if descriptions:
        context += "Column descriptions:\n"
        for col, desc in descriptions.items():
            if desc:
                context += f"- {col}: {desc}\n"
        context += "\n"
    
    if any(word in question_lower for word in ['rows', 'row', 'records', 'entries', 'count']):
        if 'rows' in question_lower or 'records' in question_lower or 'entries' in question_lower:
            return f"{context}Total number of rows: {len(df):,}"
        
        if 'columns' in question_lower or 'fields' in question_lower:
            if 'list' in question_lower or 'show' in question_lower:
                result = "Available columns:\n\n"
                for col in df.columns:
                    desc = descriptions.get(col, "")
                    col_type = df[col].dtype
                    result += f"📊 {col} ({col_type})"
                    if desc:
                        result += f"\n   Description: {desc}"
                    result += "\n"
                return result
            return f"{context}Total number of columns: {len(df.columns)}"
    
    for col in df.columns:
        if col.lower() in question_lower or col.replace('_', ' ').lower() in question_lower:
            desc = descriptions.get(col, "")
            
            if df[col].dtype in ['int64', 'float64']:
                if 'min' in question_lower or 'minimum' in question_lower:
                    return f"{context}Minimum value in '{col}': {df[col].min():.2f}"
                elif 'max' in question_lower or 'maximum' in question_lower:
                    return f"{context}Maximum value in '{col}': {df[col].max():.2f}"
                elif 'average' in question_lower or 'mean' in question_lower:
                    return f"{context}Average value in '{col}': {df[col].mean():.2f}"
                elif 'sum' in question_lower or 'total' in question_lower:
                    return f"{context}Sum of '{col}': {df[col].sum():.2f}"
            else:
                if 'most common' in question_lower or 'frequent' in question_lower:
                    top_value = df[col].value_counts().index[0]
                    top_count = df[col].value_counts().iloc[0]
                    return f"{context}Most common value in '{col}': '{top_value}' ({top_count:,} occurrences)"
                
                if 'unique' in question_lower:
                    unique_values = df[col].nunique()
                    return f"{context}Column '{col}' has {unique_values:,} unique values."
    
    if 'summary' in question_lower or 'statistics' in question_lower or 'stats' in question_lower:
        result = f"{context}Dataset Summary:\n"
        result += f"📊 Table: {table_name}\n"
        result += f"📈 Total Rows: {len(df):,}\n"
        result += f"📋 Total Columns: {len(df.columns)}\n\n"
        
        for col in df.columns:
            desc = descriptions.get(col, "")
            col_type = df[col].dtype
            null_count = df[col].isnull().sum()
            result += f"• {col} ({col_type})"
            if desc:
                result += f" - {desc}"
            result += f"\n  Missing: {null_count:,} ({null_count/len(df)*100:.1f}%)"
            
            if df[col].dtype in ['int64', 'float64']:
                result += f"\n  Mean: {df[col].mean():.2f}, Min: {df[col].min():.2f}, Max: {df[col].max():.2f}"
            result += "\n"
        return result
    
    return f"I can help you analyze this dataset. You can ask about:\n" + \
           f"• Row/column counts\n" + \
           f"• Column details and descriptions\n" + \
           f"• Statistics (min, max, average, sum)\n" + \
           f"• Unique values\n" + \
           f"• Missing values\n" + \
           f"• Summary statistics\n\n" + \
           f"Try asking: 'How many rows?', 'List columns', 'Average of [column]', or 'Show me summary statistics'"

@app.get("/health")
async def health_check():
    llm_status = "disabled"
    if llm:
        llm_status = "connected"
    elif USE_LLM and llm_init_error:
        llm_status = "error"
    
    return {
        "status": "healthy",
        "table": current_table_name,
        "rows": int(len(uploaded_df)) if uploaded_df is not None else 0,
        "llm": {
            "enabled": LLM_ENABLED,
            "requested": USE_LLM,
            "model": GROQ_MODEL,
            "status": llm_status,
            "error": llm_init_error
        }
    }

@app.delete("/data")
async def clear_data():
    global uploaded_df, current_table_name, current_columns, column_descriptions, user_prompt, current_session_id
    uploaded_df = None
    current_table_name = None
    current_columns = []
    column_descriptions = {}
    user_prompt = None
    current_session_id = None
    return {"message": "Data cleared successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)