import os
import re
import sqlite3
import asyncio
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager

# Vanna Specific Imports
from vanna_setup import vanna_agent
from vanna.core.user import User, RequestContext

# --- Step 1: SQL Security & Validation ---
def is_sql_safe(sql: str) -> bool:
    """Blocks destructive commands to prevent SQL Injection."""
    if not sql: 
        return False
    
    # List of prohibited keywords for a 'Read-Only' assistant
    forbidden = [
        "DROP", "DELETE", "INSERT", "UPDATE", "ALTER", 
        "TRUNCATE", "EXEC", "GRANT", "REVOKE", "ATTACH"
    ]
    
    sql_upper = sql.upper().strip()
    
    # Must start with SELECT and contain none of the forbidden words
    return sql_upper.startswith("SELECT") and not any(w in sql_upper for w in forbidden)

# --- Step 2: Server Lifespan (Auto-Seeding) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes the AI memory with core clinic business logic on startup."""
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
        # Prevent CPU spikes on local hardware during initialization
        await asyncio.sleep(0.5) 
        
    print("✅ Memory seeded. Ready for chats!")
    yield

# --- Step 3: FastAPI Configuration ---
app = FastAPI(title="Clinic AI Database Assistant", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    question: str

# --- Step 4: The Chat Endpoint ---
# --- Step 4: The Chat Endpoint ---
@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    context = RequestContext(user=User(id="admin_user", name="Analyst", group_memberships=['admin', 'user']))
    
    generated_sql = None
    results_df = None
    summary_text = ""
    
    print(f"\n--- INCOMING REQUEST: {request.question} ---")

    # System prompt to guide the local model
    prompt = f"""You are a SQLite database expert. Write a valid SQL query to answer the question.
    Wrap your SQL query inside a markdown block: ```sql\nSELECT ...\n```
    Question: {request.question}"""

    try:
        # Stream the response from the Vanna Agent
        async for component in vanna_agent.send_message(request_context=context, message=prompt):
            comp_type = type(component).__name__
            
            # THE FIX: We use str(component) to X-Ray the raw Vanna objects so we don't miss the SQL!
            raw_data = getattr(component, 'text', getattr(component, 'content', str(component)))
            
            if comp_type not in ['StatusBarUpdateComponent', 'TaskTrackerUpdateComponent', 'ChatInputUpdateComponent']:
                if raw_data: 
                    summary_text += str(raw_data) + " "

        # --- THE SANITIZED FALLBACK LOGIC ---
        if summary_text:
            # Extract SQL using Regex
            sql_match = re.search(r"```sql\s+(.*?)\s+```", summary_text, re.IGNORECASE | re.DOTALL)
            if not sql_match:
                sql_match = re.search(r"(SELECT\s+.*?(?:;|$))", summary_text, re.IGNORECASE | re.DOTALL)

            if sql_match:
                potential_sql = sql_match.group(1).strip()
                
                # CLEANER: Remove MySQL-style backticks and stray markdown tokens
                sanitized_sql = potential_sql.replace("```sql", "").replace("```", "").replace("`", "").strip()
                
                if is_sql_safe(sanitized_sql):
                    generated_sql = sanitized_sql
                    
                    # NATIVE EXECUTION: Bypass framework wrappers for stability
                    db_path = os.getenv("DATABASE_PATH")
                    conn = sqlite3.connect(db_path)
                    
                    # Convert SQL results directly to a DataFrame
                    results_df = pd.read_sql_query(generated_sql, conn)
                    conn.close()
                    
                    print(f"✅ Executed SQL: {generated_sql}")
                    summary_text = "Database query executed successfully."

        if not generated_sql:
             return {"error": "SQL Generation Failed", "details": f"The AI did not provide a valid query. Output: {summary_text[:100]}..."}

        return {
            "message": summary_text.strip(),
            "sql_query": generated_sql,
            "columns": list(results_df.columns) if results_df is not None else [],
            "rows": results_df.values.tolist() if results_df is not None else [],
            "row_count": len(results_df) if results_df is not None else 0,
            "chart": None,
            "chart_type": None
        }
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {str(e)}")
        return {"error": "Internal Server Error", "details": str(e)}
if __name__ == "__main__":
    import uvicorn
    # Use 0.0.0.0 to allow access from other devices on your local network
    uvicorn.run(app, host="0.0.0.0", port=8000)