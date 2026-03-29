# testNLIDB

Streamlit app that converts natural language to safe SELECT SQL for PostgreSQL (Supabase compatible), then runs the query and shows results in a dataframe.

## Features

- Natural language input box
- Generate SQL button (AI powered)
- SQL preview and editable SQL text area
- Validation that blocks non-SELECT and unsafe SQL
- Run Query button with results rendered in a pandas dataframe
- Error handling for AI and database failures

## Project Structure

- `app.py`: Streamlit app with modular functions
- `requirements.txt`: Python dependencies
- `.env.example`: Required environment variables

## How to run

1. Open PowerShell in this project folder.
2. Create a virtual environment:

	```powershell
	py -m venv .venv
	```

3. Activate it:

	```powershell
	.\.venv\Scripts\Activate.ps1
	```

4. Install dependencies:

	```powershell
	pip install -r requirements.txt
	```

5. Copy environment template:

	```powershell
	Copy-Item .env.example .env
	```

6. Edit `.env` and fill your DB + AI keys.

## How to connect your database

Set these values in `.env`:

- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`

For Supabase, common values are:

- `DB_NAME=postgres`
- `DB_HOST=<your-project-ref>.supabase.co`
- `DB_PORT=5432`
- `DB_USER` and `DB_PASSWORD` from your Supabase database credentials

Choose AI provider in `.env`:

- `AI_PROVIDER=openai` with `OPENAI_API_KEY`
- or `AI_PROVIDER=gemini` with `GEMINI_API_KEY`

Then start the app:

```powershell
streamlit run app.py
```

## Important safety: prevent write/delete/edit

This app already has 3 protections:

1. SQL validation only allows single-statement `SELECT` queries.
2. Forbidden keywords are blocked (`INSERT`, `UPDATE`, `DELETE`, `DROP`, etc.).
3. Query execution is forced into a read-only transaction.

For strongest protection, also use a read-only database user.

### Create a read-only role (PostgreSQL)

Run this in your SQL editor (adjust username/password/schema):

```sql
CREATE ROLE nlidb_readonly WITH LOGIN PASSWORD 'change-this-password';

GRANT CONNECT ON DATABASE postgres TO nlidb_readonly;
GRANT USAGE ON SCHEMA public TO nlidb_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO nlidb_readonly;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT ON TABLES TO nlidb_readonly;
```

Then put this read-only user in `.env`:

- `DB_USER=nlidb_readonly`
- `DB_PASSWORD=<readonly-password>`

This ensures that even if a bad SQL somehow slips through, the DB account itself cannot write/delete.

## Notes

- The app attempts to read schema from `information_schema.columns`.
- If schema introspection is restricted, set `DB_SCHEMA` manually in `.env`.
- SQL execution uses `pandas.read_sql_query()` over a `psycopg2` connection.
- Safety checks reject statements that are not SELECT or contain forbidden write/DDL keywords.
