import os
import re

import pandas as pd
import psycopg2
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

FORBIDDEN_SQL_PATTERNS = [
    r"\binsert\b",
    r"\bupdate\b",
    r"\bdelete\b",
    r"\bdrop\b",
    r"\balter\b",
    r"\btruncate\b",
    r"\bcreate\b",
    r"\bgrant\b",
    r"\brevoke\b",
]


def get_db_config() -> dict:
    return {
        "dbname": os.getenv("DB_NAME", ""),
        "user": os.getenv("DB_USER", ""),
        "password": os.getenv("DB_PASSWORD", ""),
        "host": os.getenv("DB_HOST", ""),
        "port": os.getenv("DB_PORT", "5432"),
    }


def get_db_connection() -> psycopg2.extensions.connection:
    config = get_db_config()
    required_env = ["DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST"]
    missing = [name for name in required_env if not os.getenv(name, "").strip()]
    if missing:
        raise ValueError(
            "Missing required database environment variables: "
            + ", ".join(missing)
        )
    return psycopg2.connect(**config)


def get_schema_description() -> str:
    schema_env = os.getenv("DB_SCHEMA", "").strip()
    if schema_env:
        return schema_env

    schema_query = """
    SELECT
        table_schema,
        table_name,
        column_name,
        data_type
    FROM information_schema.columns
    WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
    ORDER BY table_schema, table_name, ordinal_position;
    """

    try:
        with get_db_connection() as conn:
            df = pd.read_sql_query(schema_query, conn)
    except Exception as exc:
        return (
            "Schema could not be loaded automatically. "
            f"Error: {exc}. Use DB_SCHEMA env var to provide schema manually."
        )

    if df.empty:
        return "No tables found in accessible schemas."

    lines = []
    current_table = None
    for row in df.itertuples(index=False):
        table_label = f"{row.table_schema}.{row.table_name}"
        if table_label != current_table:
            current_table = table_label
            lines.append(f"Table: {table_label}")
        lines.append(f"  - {row.column_name} ({row.data_type})")

    return "\n".join(lines)


def call_openai(prompt: str) -> str:
    from openai import OpenAI
    from openai import APIStatusError, RateLimitError

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing.")

    client = OpenAI(api_key=api_key)
    try:
        response = client.responses.create(
            model=model,
            input=prompt,
            temperature=0,
        )
    except RateLimitError as exc:
        raise RuntimeError(
            "OpenAI quota/rate limit reached (429). Add billing/credits or switch provider."
        ) from exc
    except APIStatusError as exc:
        if exc.status_code == 429:
            raise RuntimeError(
                "OpenAI quota/rate limit reached (429). Add billing/credits or switch provider."
            ) from exc
        raise RuntimeError(f"OpenAI API error ({exc.status_code}).") from exc

    text = (response.output_text or "").strip()
    if not text:
        raise RuntimeError("OpenAI returned an empty response.")
    return text


def call_gemini(prompt: str) -> str:
    import google.generativeai as genai

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing.")

    genai.configure(api_key=api_key)  # type: ignore[attr-defined]
    try:
        response = genai.GenerativeModel(model).generate_content(prompt)  # type: ignore[attr-defined]
    except Exception as exc:
        error_text = str(exc).lower()
        if "429" in error_text or "quota" in error_text or "resourceexhausted" in error_text:
            raise RuntimeError(
                "Gemini quota/rate limit reached (429). Enable billing/credits or switch provider."
            ) from exc
        raise RuntimeError(f"Gemini API error: {exc}") from exc

    text = (response.text or "").strip()
    if not text:
        raise RuntimeError("Gemini returned an empty response.")
    return text


def clean_model_sql_output(raw_output: str) -> str:
    text = raw_output.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = re.sub(r"^sql\n", "", text, flags=re.IGNORECASE)
    return text.strip()


def generate_sql(nl_query: str) -> str:
    schema = get_schema_description()

    prompt = f"""
You are a PostgreSQL SQL assistant.
Translate the user request into ONE safe SQL query.
Rules:
1) Return ONLY SQL with no explanation, no markdown.
2) Query must be SELECT-only.
3) Do not use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, GRANT, or REVOKE.
4) Use PostgreSQL syntax.
5) Use LIMIT 200 unless the user explicitly asks for a different limit.

Database schema:
{schema}

User request:
{nl_query}
""".strip()

    provider = os.getenv("AI_PROVIDER", "openai").strip().lower()

    if provider == "gemini":
        raw_sql = call_gemini(prompt)
    else:
        raw_sql = call_openai(prompt)

    return clean_model_sql_output(raw_sql)


def validate_sql(sql_query: str) -> tuple[bool, str]:
    sql = sql_query.strip()

    if not sql:
        return False, "Generated SQL is empty."

    if sql.endswith(";"):
        sql = sql[:-1].strip()

    if ";" in sql:
        return False, "Only one SQL statement is allowed."

    if not sql.lower().startswith("select"):
        return False, "Only SELECT queries are allowed."

    for pattern in FORBIDDEN_SQL_PATTERNS:
        if re.search(pattern, sql, flags=re.IGNORECASE):
            return False, "Unsafe SQL detected (contains forbidden keywords)."

    return True, "SQL is valid."


def run_query(sql_query: str) -> pd.DataFrame:
    with get_db_connection() as conn:
        # Defense in depth: force the connection transaction to read-only.
        conn.set_session(readonly=True, autocommit=False)
        with conn.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
        return pd.read_sql_query(sql_query, conn)


def app() -> None:
    st.set_page_config(page_title="NL to SQL", layout="wide")
    st.title("Natural Language to SQL (PostgreSQL / Supabase)")
    st.caption(
        "Ask a question in plain English, generate SELECT SQL with AI, review/edit it, then run it."
    )

    if "generated_sql" not in st.session_state:
        st.session_state.generated_sql = ""

    nl_query = st.text_area(
        "Natural language query",
        placeholder="Example: Show the top 10 customers by total order amount this month.",
        height=120,
    )

    if st.button("Generate SQL", type="primary"):
        if not nl_query.strip():
            st.warning("Please enter a natural language query first.")
        else:
            try:
                st.session_state.generated_sql = generate_sql(nl_query)
                if not st.session_state.generated_sql.strip():
                    st.warning(
                        "AI returned empty SQL. You can type a SELECT query manually below."
                    )
            except Exception as exc:
                st.error(f"Failed to generate SQL: {exc}")
                st.info(
                    "You can still paste or type a SELECT query in the editable SQL box and run it."
                )

    sql_query = st.text_area(
        "Generated SQL (editable)",
        value=st.session_state.generated_sql,
        height=180,
    )

    if sql_query.strip():
        st.subheader("SQL Preview")
        st.code(sql_query, language="sql")

    valid, message = validate_sql(sql_query) if sql_query.strip() else (False, "")

    if sql_query.strip() and not valid:
        st.warning(message)

    run_disabled = not sql_query.strip() or not valid
    if st.button("Run Query", disabled=run_disabled):
        try:
            df = run_query(sql_query)
            st.success(f"Query executed successfully. Returned {len(df)} rows.")
            st.dataframe(df, use_container_width=True)
        except Exception as exc:
            st.error(f"Database query failed: {exc}")


if __name__ == "__main__":
    app()
