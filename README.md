# DataPilot AI

DataPilot AI is a full-stack analytics workspace for exploring CSV data with a chat interface. It lets you upload a CSV file, profile its columns, attach business context, persist the dataset to MySQL, and then ask natural-language questions that are answered with SQL-backed results.

The application combines:

- An Angular frontend for dataset upload, table selection, session history, and chat
- A FastAPI backend for file ingestion, metadata persistence, chat orchestration, and API endpoints
- MySQL for dataset storage, metadata, users, chat sessions, and chat history
- Optional Groq-backed LLM support through LangChain for SQL generation and answer summarization

## Features

- Upload CSV files and preview the data before saving
- Sanitize column names for SQL-safe storage
- Add per-column descriptions to explain business meaning
- Add a dataset-level prompt for extra analysis context
- Persist uploaded datasets as MySQL tables
- Create and reopen named chat sessions per dataset
- Ask natural-language questions and receive answers with generated SQL
- Show structured SQL result previews for scalar and tabular answers
- Fall back to rule-based analytics when LLM support is unavailable
- Keep chat history and session activity in the database

## Architecture

### Frontend

- Framework: Angular 20
- Main workspace UI: upload flow, dataset browser, session history, chat panel
- Default local URL: `http://localhost:4200`

### Backend

- Framework: FastAPI
- Default local URL: `http://localhost:8000`
- CORS enabled for local Angular development ports

### Database

- Engine: MySQL via SQLAlchemy and PyMySQL
- Default database name: `datapilot`
- Stores uploaded tables plus supporting metadata tables

### AI Layer

- Provider: Groq through `langchain-groq`
- Default model: `openai/gpt-oss-120b`
- Optional: the app still works without an API key, but responses are limited to rule-based behavior

## Repository Structure

```text
data-pilot-ai/
|-- backend/
|   |-- app.py
|   |-- db.py
|   |-- load_data.py
|   |-- model.py
|   |-- requirements.txt
|   `-- services/
|       |-- common.py
|       |-- session_service.py
|       |-- sql_chat_service.py
|       `-- table_service.py
|-- frontend/
|   |-- angular.json
|   |-- package.json
|   |-- public/
|   `-- src/
`-- README.md
```

## How It Works

1. Upload a CSV file from the Angular UI.
2. The backend reads the file with pandas and profiles each column.
3. You optionally add column descriptions and a dataset prompt.
4. The dataset is persisted to MySQL as a table.
5. A matching metadata table and prompt table are created when needed.
6. You select the table and start a chat session.
7. The backend answers questions using either:
	 - direct table-context responses for schema and dataset questions,
	 - rule-based SQL generation for common analytics prompts, or
	 - LLM-generated SQL when Groq is configured.
8. Chat history, SQL, and result payloads are stored for future sessions.

## Data Model

For each uploaded dataset table such as `sales_2026`, the backend may create:

- `sales_2026`: the actual uploaded dataset
- `sales_2026_metadata`: column descriptions
- `sales_2026_prompt`: dataset-level context prompt

The backend also manages these internal tables:

- `app_users`
- `chat_sessions`
- `chat_history`

## Prerequisites

Install these before running the app:

- Python 3.10+
- Node.js 20+ and npm
- MySQL 8+
- A Groq API key if you want LLM-powered SQL generation and summarization

## Environment Configuration

The backend loads environment variables from a `.env` file if present.

Example configuration:

```env
DB_USER=root
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=3306
DB_NAME=datapilot

USE_LLM=true
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-120b

APP_DEFAULT_USER_NAME=Data Analyst
APP_DEFAULT_USER_EMAIL=analyst@datapilot.local
APP_DEFAULT_USER_INITIALS=DA
```

### Notes

- If `USE_LLM=true` but `GROQ_API_KEY` is missing, the backend disables LLM features automatically.
- If `USE_LLM=false`, the app uses only context-based and rule-based responses.
- The current backend code includes a hard-coded fallback MySQL password in `db.py`; override it with environment variables in any real environment.

## Local Setup

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd data-pilot-ai
```

### 2. Create the MySQL database

```sql
CREATE DATABASE datapilot;
```

If you want to use a different database name, update `DB_NAME` in your environment.

### 3. Start the backend

From the `backend` directory:

```bash
python -m venv .venv
```

Activate the virtual environment.

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the API:

```bash
python app.py
```

The backend starts on `http://localhost:8000`.

### 4. Start the frontend

From the `frontend` directory:

```bash
npm install
npm start
```

The frontend starts on `http://localhost:4200`.

## Running the Application

1. Open the frontend in your browser.
2. Click `Upload CSV`.
3. Choose a `.csv` file.
4. Enter a valid table name.
5. Inspect the detected columns.
6. Add optional column descriptions.
7. Add an optional dataset prompt.
8. Save the table.
9. Select the table from the sidebar.
10. Start a new session or open an existing one.
11. Ask questions such as:
		- `How many rows are in this table?`
		- `List the columns and what they mean.`
		- `What is the average revenue?`
		- `Which category appears most often?`
		- `Show the first 5 rows.`

## API Overview

### Health and user

- `GET /health`: backend status, active table, row count, and LLM status
- `GET /me`: returns the default application user

### Table ingestion and selection

- `POST /upload`: uploads and profiles a CSV file
- `POST /create-table`: persists the uploaded dataframe and metadata
- `POST /table/select`: loads an existing dataset table into the active workspace
- `GET /tables`: lists dataset tables available to the current user context
- `DELETE /data`: clears the backend's in-memory active selection state

### Sessions and history

- `GET /sessions`: lists chat sessions, optionally filtered by table name and user ID
- `POST /sessions`: creates a new chat session
- `POST /sessions/select`: selects an existing chat session
- `GET /history`: returns chat history for a session or table

### Chat

- `POST /chat`: answers a natural-language question and may return:
	- `answer`
	- `sql_query`
	- `session_id`
	- `result_payload`

## Example API Requests

### Upload a CSV

```bash
curl -X POST "http://localhost:8000/upload?table_name=customers_2026" \
	-F "file=@customers.csv"
```

### Create a table with metadata

```bash
curl -X POST "http://localhost:8000/create-table" \
	-H "Content-Type: application/json" \
	-d '{
		"table_name": "customers_2026",
		"column_descriptions": [
			{"column_name": "customer_id", "description": "Unique customer identifier"},
			{"column_name": "revenue", "description": "Total customer revenue"}
		],
		"prompt": "Customer dataset for FY2026 revenue analysis"
	}'
```

### Ask a question

```bash
curl -X POST "http://localhost:8000/chat" \
	-H "Content-Type: application/json" \
	-d '{
		"question": "What is the average revenue?",
		"table_name": "customers_2026"
	}'
```

## Supported Question Types

The current implementation is strongest on:

- Row counts and basic dataset stats
- Column listing and column description lookups
- Dataset prompt/context questions
- First-row preview requests
- Aggregations such as average, sum, minimum, and maximum
- Frequency questions such as most common category
- Follow-up questions when a session has recent SQL history

## Current Constraints

- Only CSV uploads are supported by the backend.
- Table names must match the pattern `^[a-zA-Z_][a-zA-Z0-9_]*$`.
- SQL execution is intentionally restricted to read-only `SELECT` and `WITH` queries.
- The backend keeps some active table state in process memory, so it is designed for local development or simple single-instance use.
- LLM quality depends on your Groq model and prompt context.
- Large datasets may require MySQL tuning and careful indexing outside the current implementation.

## Troubleshooting

### Frontend cannot reach the backend

- Make sure the FastAPI server is running on port `8000`.
- Confirm the frontend is running on `4200` or another CORS-allowed local port.

### MySQL connection fails

- Verify your MySQL server is running.
- Confirm `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, and `DB_NAME` are correct.
- Make sure the target database exists.

### LLM features are disabled

- Check that `USE_LLM=true`.
- Set a valid `GROQ_API_KEY`.
- Call `GET /health` and inspect the `llm` section.

### Upload fails

- Confirm the file is a valid CSV.
- Confirm the CSV is not empty.
- Confirm the table name is valid.

## Development Notes

- The frontend uses Angular standalone components.
- The backend stores both chat text and generated SQL for session replay.
- Result payloads are persisted as JSON in MySQL.
- Session titles are auto-generated from the first meaningful user question when possible.

## Future Improvements

- Add `.env.example` and Docker-based local setup
- Add authentication and real multi-user support
- Add automated tests for API and UI flows
- Add support for Excel uploads if required
- Add chart rendering for query results
- Improve production readiness by removing in-memory active state

## License

This project is distributed under the terms of the license in [LICENSE](LICENSE).
