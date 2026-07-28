from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from fastapi.middleware.cors import CORSMiddleware
from io import BytesIO
import pandas as pd
import os
from dotenv import load_dotenv
from model import ChatRequest
import re

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

# Create database engine
def get_engine():
    return create_engine(
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
        pool_pre_ping=True,
        pool_recycle=3600
    )

# Store current dataframe and table info
uploaded_df = None
current_table_name = None
current_columns = []

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    table_name: str = Query(..., description="Name of the table to create")
):
    global uploaded_df, current_table_name, current_columns
    
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    # Validate table name
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
        raise HTTPException(status_code=400, detail="Invalid table name. Use only letters, numbers, and underscores")
    
    try:
        # Read CSV content
        content = await file.read()
        df = pd.read_csv(BytesIO(content))
        
        # Validate data
        if df.empty:
            raise HTTPException(status_code=400, detail="CSV file is empty")
        
        # Clean column names (replace spaces, special characters)
        df.columns = [re.sub(r'[^a-zA-Z0-9_]', '_', col) for col in df.columns]
        
        # Store in global variable for chat queries
        uploaded_df = df
        current_table_name = table_name
        current_columns = df.columns.tolist()
        
        # Create database connection and insert data
        engine = get_engine()
        
        # Insert data into MySQL
        df.to_sql(
            name=table_name,
            con=engine,
            if_exists="replace",
            index=False,
            chunksize=10000  # Chunk size for large datasets
        )
        
        # Get preview data (first 5 rows)
        preview = df.head(5).fillna("").to_dict(orient='records')
        
        return {
            "success": True,
            "message": f"Successfully uploaded {len(df)} rows to table '{table_name}'",
            "columns": current_columns,
            "preview": preview,
            "row_count": len(df),
            "table_name": table_name
        }
        
    except pd.errors.EmptyDataError:
        raise HTTPException(status_code=400, detail="CSV file is empty or invalid")
    except pd.errors.ParserError:
        raise HTTPException(status_code=400, detail="Invalid CSV format")
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@app.post("/chat")
async def chat(request: ChatRequest):
    global uploaded_df, current_table_name, current_columns
    
    if uploaded_df is None:
        return {
            "answer": "No dataset uploaded yet. Please upload a CSV file first."
        }
    
    question = request.question.lower().strip()
    
    # Parse natural language questions
    try:
        answer = process_question(question, uploaded_df, current_table_name)
        return {"answer": answer}
    except Exception as e:
        return {"answer": f"Error processing your question: {str(e)}"}

def process_question(question: str, df: pd.DataFrame, table_name: str):
    """Process natural language questions about the dataset"""
    
    # Row count questions
    if any(word in question for word in ['rows', 'row', 'records', 'entries', 'count', 'how many']):
        if 'rows' in question or 'records' in question or 'entries' in question:
            return f"Total number of rows: {len(df):,}"
        
        if 'columns' in question or 'fields' in question:
            return f"Total number of columns: {len(df.columns)}"
    
    # Column information
    if any(word in question for word in ['columns', 'fields', 'attributes']):
        if 'list' in question or 'show' in question or 'what' in question:
            columns_list = ', '.join(df.columns.tolist())
            return f"Available columns: {columns_list}"
    
    # Unique values
    if 'unique' in question or 'distinct' in question:
        # Find which column
        for col in df.columns:
            if col.lower() in question or col.replace('_', ' ').lower() in question:
                unique_values = df[col].nunique()
                sample = df[col].dropna().unique()[:5].tolist()
                return f"Column '{col}' has {unique_values:,} unique values. Sample values: {sample}"
    
    # Null/missing values
    if any(word in question for word in ['null', 'missing', 'empty', 'na']):
        null_counts = df.isnull().sum()
        null_columns = null_counts[null_counts > 0]
        if len(null_columns) == 0:
            return "No null values found in the dataset."
        result = "Columns with missing values:\n"
        for col, count in null_columns.items():
            percentage = (count / len(df)) * 100
            result += f"- {col}: {count:,} missing ({percentage:.1f}%)\n"
        return result
    
    # Summary statistics
    if any(word in question for word in ['summary', 'statistics', 'stats', 'describe']):
        numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns
        if len(numeric_cols) > 0:
            stats = df[numeric_cols].describe()
            result = "Summary statistics for numeric columns:\n"
            for col in numeric_cols[:5]:  # Limit to 5 columns
                result += f"\n{col}:\n"
                result += f"  Mean: {stats[col]['mean']:.2f}\n"
                result += f"  Min: {stats[col]['min']:.2f}\n"
                result += f"  Max: {stats[col]['max']:.2f}\n"
            return result
        else:
            return "No numeric columns found for summary statistics."
    
    # Column-specific queries
    for col in df.columns:
        if col.lower() in question or col.replace('_', ' ').lower() in question:
            # Check for min/max/average
            if df[col].dtype in ['int64', 'float64']:
                if 'min' in question or 'minimum' in question or 'lowest' in question:
                    return f"Minimum value in '{col}': {df[col].min():.2f}"
                elif 'max' in question or 'maximum' in question or 'highest' in question:
                    return f"Maximum value in '{col}': {df[col].max():.2f}"
                elif 'average' in question or 'mean' in question:
                    return f"Average value in '{col}': {df[col].mean():.2f}"
                elif 'sum' in question or 'total' in question:
                    return f"Sum of '{col}': {df[col].sum():.2f}"
                elif 'median' in question:
                    return f"Median of '{col}': {df[col].median():.2f}"
            else:
                # Categorical column
                if 'most common' in question or 'frequent' in question:
                    top_value = df[col].value_counts().index[0]
                    top_count = df[col].value_counts().iloc[0]
                    return f"Most common value in '{col}': '{top_value}' ({top_count:,} occurrences)"
    
    # General data info
    if any(word in question for word in ['info', 'information', 'about', 'describe']):
        return f"Dataset has {len(df):,} rows and {len(df.columns)} columns.\nColumns: {', '.join(df.columns.tolist())}"
    
    # Default response
    return f"I understand you're asking about the dataset. I can help with:\n" \
           f"- Row/column count\n" \
           f"- Column names and types\n" \
           f"- Summary statistics\n" \
           f"- Unique values\n" \
           f"- Missing values\n" \
           f"- Specific column queries (min, max, average, sum)\n\n" \
           f"Try asking: 'How many rows?', 'List columns', 'Summary statistics', or 'What is the average of [column_name]?'"

@app.get("/health")
async def health_check():
    return {"status": "healthy", "table": current_table_name, "rows": len(uploaded_df) if uploaded_df is not None else 0}

@app.delete("/data")
async def clear_data():
    global uploaded_df, current_table_name, current_columns
    uploaded_df = None
    current_table_name = None
    current_columns = []
    return {"message": "Data cleared successfully"}