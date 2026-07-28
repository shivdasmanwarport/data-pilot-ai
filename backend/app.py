from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Body
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from fastapi.middleware.cors import CORSMiddleware
from io import BytesIO
import pandas as pd
import os
import re
import json
from pathlib import Path
from dotenv import load_dotenv
from model import ChatRequest, TableCreationRequest, ColumnDescription
from typing import Optional, Dict, Any
import numpy as np

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://localhost:4201", "http://127.0.0.1:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database configuration
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Shiv%402001")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "datapilot")

def get_engine():
    return create_engine(
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
        pool_pre_ping=True,
        pool_recycle=3600
    )

# Helper function to convert numpy types to Python native types
def convert_numpy_types(obj):
    """Convert numpy types to Python native types for JSON serialization"""
    if isinstance(obj, (np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    elif isinstance(obj, (np.float64, np.float32, np.float16)):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, pd.Series):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    else:
        return obj

# Store metadata
uploaded_df = None
current_table_name = None
current_columns = []
column_descriptions = {}
user_prompt = None

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    table_name: str = Query(..., description="Name of the table to create")
):
    global uploaded_df, current_table_name, current_columns, column_descriptions, user_prompt
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
        raise HTTPException(status_code=400, detail="Invalid table name. Use only letters, numbers, and underscores")
    
    try:
        content = await file.read()
        df = pd.read_csv(BytesIO(content))
        
        if df.empty:
            raise HTTPException(status_code=400, detail="CSV file is empty")
        
        # Clean column names
        original_columns = df.columns.tolist()
        df.columns = [re.sub(r'[^a-zA-Z0-9_]', '_', col) for col in df.columns]
        
        # Store data
        uploaded_df = df
        current_table_name = table_name
        current_columns = df.columns.tolist()
        column_descriptions = {}
        user_prompt = None
        
        # Get column info - convert numpy types to Python native
        column_info = []
        for col in df.columns:
            col_type = str(df[col].dtype)
            sample_values = df[col].dropna().head(3).tolist()
            # Convert any numpy types in sample values
            sample_values = convert_numpy_types(sample_values)
            null_count = int(df[col].isnull().sum())  # Convert to int
            unique_count = int(df[col].nunique())  # Convert to int
            
            column_info.append({
                "name": col,
                "original_name": original_columns[df.columns.tolist().index(col)] if col in df.columns else col,
                "type": col_type,
                "sample_values": sample_values,
                "null_count": null_count,
                "unique_count": unique_count,
                "description": ""  # User will fill this
            })
        
        # Convert preview data to JSON serializable format
        preview = df.head(5).fillna("").to_dict(orient='records')
        preview = convert_numpy_types(preview)
        
        return {
            "success": True,
            "message": f"Successfully uploaded {len(df)} rows from '{file.filename}'",
            "columns": current_columns,
            "column_info": column_info,
            "preview": preview,
            "row_count": int(len(df)),  # Convert to int
            "table_name": table_name
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@app.post("/create-table")
async def create_table_with_metadata(request: TableCreationRequest = Body(...)):
    global uploaded_df, current_table_name, current_columns, column_descriptions, user_prompt
    
    if uploaded_df is None:
        raise HTTPException(status_code=400, detail="No data uploaded. Please upload a CSV file first.")
    
    try:
        # Store column descriptions
        column_descriptions = {}
        for col_desc in request.column_descriptions:
            column_descriptions[col_desc.column_name] = col_desc.description
        
        # Store user prompt
        user_prompt = request.prompt
        
        # Create table in MySQL with descriptions stored as metadata
        engine = get_engine()
        
        # Insert data into MySQL
        uploaded_df.to_sql(
            name=current_table_name,
            con=engine,
            if_exists="replace",
            index=False,
            chunksize=10000
        )
        
        # Store column descriptions and prompt in a metadata table
        metadata_table_name = f"{current_table_name}_metadata"
        
        # Create metadata table if it doesn't exist
        create_metadata_table = text(f"""
            CREATE TABLE IF NOT EXISTS {metadata_table_name} (
                id INT AUTO_INCREMENT PRIMARY KEY,
                table_name VARCHAR(255),
                column_name VARCHAR(255),
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_column (table_name, column_name)
            )
        """)
        
        with engine.connect() as conn:
            conn.execute(create_metadata_table)
            
            # Insert column descriptions
            for col, desc in column_descriptions.items():
                if desc:  # Only insert if description is not empty
                    insert_sql = text(f"""
                        INSERT INTO {metadata_table_name} (table_name, column_name, description)
                        VALUES (:table_name, :column_name, :description)
                        ON DUPLICATE KEY UPDATE description = :description
                    """)
                    conn.execute(insert_sql, {
                        "table_name": current_table_name,
                        "column_name": col,
                        "description": desc
                    })
            
            # Store prompt in a separate table
            prompt_table_name = f"{current_table_name}_prompt"
            create_prompt_table = text(f"""
                CREATE TABLE IF NOT EXISTS {prompt_table_name} (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    table_name VARCHAR(255) UNIQUE,
                    prompt TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """)
            conn.execute(create_prompt_table)
            
            if user_prompt:
                insert_prompt = text(f"""
                    INSERT INTO {prompt_table_name} (table_name, prompt)
                    VALUES (:table_name, :prompt)
                    ON DUPLICATE KEY UPDATE prompt = :prompt, updated_at = CURRENT_TIMESTAMP
                """)
                conn.execute(insert_prompt, {
                    "table_name": current_table_name,
                    "prompt": user_prompt
                })
            
            conn.commit()
        
        return {
            "success": True,
            "message": f"Table '{current_table_name}' created successfully with metadata!",
            "table_name": current_table_name,
            "row_count": int(len(uploaded_df)),
            "column_count": int(len(current_columns)),
            "column_descriptions": column_descriptions,
            "prompt": user_prompt
        }
        
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating table: {str(e)}")

@app.post("/chat")
async def chat(request: ChatRequest):
    global uploaded_df, current_table_name, current_columns, column_descriptions, user_prompt
    
    if uploaded_df is None:
        return {
            "answer": "No dataset uploaded yet. Please upload a CSV file first."
        }
    
    question = request.question.lower().strip()
    
    try:
        answer = process_question_with_metadata(question, uploaded_df, current_table_name, column_descriptions, user_prompt)
        return {"answer": answer}
    except Exception as e:
        return {"answer": f"Error processing your question: {str(e)}"}

def process_question_with_metadata(question: str, df: pd.DataFrame, table_name: str, descriptions: Dict, prompt: Optional[str]):
    """Process natural language questions using metadata"""
    
    # Use user prompt as context if available
    context = ""
    if prompt:
        context += f"Context about the dataset: {prompt}\n\n"
    
    if descriptions:
        context += "Column descriptions:\n"
        for col, desc in descriptions.items():
            if desc:
                context += f"- {col}: {desc}\n"
        context += "\n"
    
    # Row count questions
    if any(word in question for word in ['rows', 'row', 'records', 'entries', 'count', 'how many']):
        if 'rows' in question or 'records' in question or 'entries' in question:
            return f"{context}Total number of rows: {len(df):,}"
        
        if 'columns' in question or 'fields' in question:
            return f"{context}Total number of columns: {len(df.columns)}"
    
    # Column information with descriptions
    if any(word in question for word in ['columns', 'fields', 'attributes']):
        if 'list' in question or 'show' in question or 'what' in question:
            result = "Available columns:\n\n"
            for col in df.columns:
                desc = descriptions.get(col, "")
                col_type = df[col].dtype
                result += f"📊 {col} ({col_type})"
                if desc:
                    result += f"\n   Description: {desc}"
                result += "\n"
            return result
    
    # Column-specific queries with context
    for col in df.columns:
        if col.lower() in question or col.replace('_', ' ').lower() in question:
            desc = descriptions.get(col, "")
            
            if df[col].dtype in ['int64', 'float64']:
                if 'min' in question or 'minimum' in question or 'lowest' in question:
                    return f"{context}Minimum value in '{col}': {df[col].min():.2f}\nDescription: {desc if desc else 'No description provided'}"
                elif 'max' in question or 'maximum' in question or 'highest' in question:
                    return f"{context}Maximum value in '{col}': {df[col].max():.2f}\nDescription: {desc if desc else 'No description provided'}"
                elif 'average' in question or 'mean' in question:
                    return f"{context}Average value in '{col}': {df[col].mean():.2f}\nDescription: {desc if desc else 'No description provided'}"
                elif 'sum' in question or 'total' in question:
                    return f"{context}Sum of '{col}': {df[col].sum():.2f}\nDescription: {desc if desc else 'No description provided'}"
                elif 'median' in question:
                    return f"{context}Median of '{col}': {df[col].median():.2f}\nDescription: {desc if desc else 'No description provided'}"
            else:
                if 'most common' in question or 'frequent' in question:
                    top_value = df[col].value_counts().index[0]
                    top_count = df[col].value_counts().iloc[0]
                    return f"{context}Most common value in '{col}': '{top_value}' ({top_count:,} occurrences)\nDescription: {desc if desc else 'No description provided'}"
                
                if 'unique' in question or 'distinct' in question:
                    unique_values = df[col].nunique()
                    return f"{context}Column '{col}' has {unique_values:,} unique values.\nDescription: {desc if desc else 'No description provided'}"
    
    # Complex queries using metadata
    if 'summary' in question or 'statistics' in question or 'stats' in question:
        result = f"{context}Dataset Summary:\n"
        result += f"📊 Table: {table_name}\n"
        result += f"📈 Total Rows: {len(df):,}\n"
        result += f"📋 Total Columns: {len(df.columns)}\n\n"
        
        # Add column summaries
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
    
    # If prompt is provided, use it for better understanding
    if prompt and 'describe' in question or 'explain' in question or 'overview' in question:
        return f"Dataset Context: {prompt}\n\n" + \
               f"Total rows: {len(df):,}\n" + \
               f"Columns: {', '.join(df.columns.tolist())}\n\n" + \
               f"Need more details? Try asking about specific columns or statistics."
    
    # Default response with helpful suggestions
    suggestions = []
    if descriptions:
        suggestions.append("using column descriptions")
    if prompt:
        suggestions.append("using the context provided")
    
    suggestion_text = f" ({' and '.join(suggestions)})" if suggestions else ""
    
    return f"I can help you analyze this dataset{suggestion_text}. You can ask about:\n" \
           f"• Row/column counts\n" \
           f"• Column details and descriptions\n" \
           f"• Statistics (min, max, average, sum)\n" \
           f"• Unique values\n" \
           f"• Missing values\n" \
           f"• Summary statistics\n\n" + \
           f"Try asking: 'How many rows?', 'List columns with descriptions', 'Average of [column]', or 'Show me summary statistics'"

@app.get("/metadata")
async def get_metadata():
    global current_table_name, current_columns, column_descriptions, user_prompt
    
    if current_table_name is None:
        raise HTTPException(status_code=404, detail="No table created yet")
    
    return {
        "table_name": current_table_name,
        "columns": current_columns,
        "column_descriptions": column_descriptions,
        "prompt": user_prompt
    }

@app.delete("/data")
async def clear_data():
    global uploaded_df, current_table_name, current_columns, column_descriptions, user_prompt
    uploaded_df = None
    current_table_name = None
    current_columns = []
    column_descriptions = {}
    user_prompt = None
    return {"message": "Data cleared successfully"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "table": current_table_name,
        "rows": int(len(uploaded_df)) if uploaded_df is not None else 0
    }