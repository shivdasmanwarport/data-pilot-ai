from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from io import BytesIO
import pandas as pd
from model import ChatRequest

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    content = await file.read()
    df = pd.read_csv(BytesIO(content))
    return {
        "columns": df.columns.to_list(),
        "preview": df.head(5).to_dict(orient='records'),
        "row_count": len(df)

    }

@app.post("/chat")
def chat(request:ChatRequest):
    print(request.question)
    return {
        "answer": f"You asked {request.question}"
    }