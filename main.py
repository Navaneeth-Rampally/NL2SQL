import os
import re
import inspect
import asyncio
import sqlite3
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
from vanna_setup import vanna_agent
from vanna.core.user import User, RequestContext
from vanna.integrations.sqlite import SqliteRunner 

# --- Step 1: SQL Validation Logic ---
def is_sql_safe(sql: str) -> bool:
    if not sql: return False
    forbidden = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE", "EXEC", "GRANT", "REVOKE"]
    sql_upper = sql.upper().strip()
    return sql_upper.startswith("SELECT") and not any(w in sql_upper for w in forbidden)

# --- Step 2: Lifespan for Auto-Seeding ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Server starting: Auto-seeding AI memory...")
    context = RequestContext(user=User(id="admin_user", name="Analyst", group_memberships=['admin', 'user']))
    
    core_queries = [
        ("How many patients do we have?", "SELECT COUNT(*) AS total_patients FROM patients"),
        ("List all doctors and their specializations", "SELECT name, specialization FROM doctors"),
        ("What is the total revenue?", "SELECT SUM(total_amount) AS total_revenue FROM invoices WHERE status = 'Paid'"),
        ("Show revenue by doctor", "SELECT d.name, SUM(i.total_amount) AS total_revenue FROM invoices i JOIN appointments a ON a.patient_id = i.patient_id JOIN doctors d ON d.id = a.doctor_id GROUP BY d.name ORDER BY total_revenue DESC"),
        ("Top 5 patients by spending", "SELECT p.first_name, p.last_name, SUM(i.total_amount) as total_spent FROM patients p JOIN invoices i ON p.id = i.patient_id GROUP BY p.id ORDER BY total_spent DESC LIMIT 5")
    ]
    
    for q, sql in core_queries:
        await vanna_agent.agent_memory.save_tool_usage(
            question=q, tool_name="run_sql", args={"sql": sql}, context=context, success=True
        )
        # Small delay to keep the local CPU from spiking too hard during boot
        await asyncio.sleep(1) 
        
    print("✅ Memory seeded. Ready for chats!")
    yield

app = FastAPI(title="Clinic NL2SQL Chatbot", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

class ChatRequest(BaseModel):
    question: str

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    context = RequestContext(user=User(id="admin_user", name="Analyst", group_memberships=['admin', 'user']))
    
    generated_sql = None
    results_df = None
    summary_text = ""
    
    print(f"\n--- ASKING OLLAMA: {request.question} ---")

    # Prompt forcing strict SQL output
    prompt = f"""You are a SQLite database expert. Write a valid SQL query to answer this question.
    You MUST wrap your SQL query inside a markdown block like this: ```sql\nSELECT ...\n```
    Question: {request.question}"""

    try:
        async for component in vanna_agent.send_message(request_context=context, message=prompt):
            comp_type = type(component).__name__
            
            # Extract text from the stream
            raw_data = getattr(component, 'text', getattr(component, 'content', str(component)))
            if comp_type not in ['StatusBarUpdateComponent', 'TaskTrackerUpdateComponent', 'ChatInputUpdateComponent']:
                if raw_data: summary_text += raw_data + " "

        # --- THE SANITIZED FALLBACK ---
        if summary_text:
            # 1. Try to find the SQL block
            sql_match = re.search(r"```sql\s+(.*?)\s+```", summary_text, re.IGNORECASE | re.DOTALL)
            if not sql_match:
                sql_match = re.search(r"(SELECT\s+.*?(?:;|$))", summary_text, re.IGNORECASE | re.DOTALL)

            if sql_match:
                potential_sql = sql_match.group(1).strip()
                
                # THE CLEANER: Removes backticks (`) and stray markdown that crash SQLite
                potential_sql = potential_sql.replace("```sql", "").replace("```", "").replace("`", "").strip()
                
                if is_sql_safe(potential_sql):
                    generated_sql = potential_sql
                    
                    # Native execution using sqlite3
                    db_path = os.getenv("DATABASE_PATH")
                    conn = sqlite3.connect(db_path)
                    
                    # Run the query and store in DataFrame
                    results_df = pd.read_sql_query(generated_sql, conn)
                    conn.close()
                    
                    summary_text = "Query executed successfully."

        if not generated_sql:
             return {"error": "The AI did not generate a SQL query.", "details": f"AI's raw output: {summary_text}"}

        return {
            "message": summary_text.strip() if summary_text else "Here are the database results:",
            "sql_query": generated_sql,
            "columns": list(results_df.columns) if results_df is not None else [],
            "rows": results_df.values.tolist() if results_df is not None else [],
            "row_count": len(results_df) if results_df is not None else 0,
            "chart": None,
            "chart_type": None
        }
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return {"error": "FastAPI Crash.", "details": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)