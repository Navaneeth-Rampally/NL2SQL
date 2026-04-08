import os
import re
import inspect # <--- Added for async checking
import asyncio
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
from vanna_setup import vanna_agent
from vanna.core.user import User, RequestContext
from vanna.integrations.sqlite import SqliteRunner 

# --- Step 7: SQL Validation Logic ---
def is_sql_safe(sql: str) -> bool:
    if not sql: return False
    forbidden = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE", "EXEC", "GRANT", "REVOKE"]
    sql_upper = sql.upper().strip()
    return sql_upper.startswith("SELECT") and not any(w in sql_upper for w in forbidden)

# --- SECURITY INTERCEPTOR (Fixed for Async Compatibility) ---
original_run_sql = SqliteRunner.run_sql

async def safe_run_sql(self, sql: str, **kwargs):
    if not is_sql_safe(sql):
        raise Exception(f"Security Violation: Rejected unsafe SQL -> {sql}")
    
    # Safely await the original function if Vanna expects it to be async
    if inspect.iscoroutinefunction(original_run_sql):
        return await original_run_sql(self, sql, **kwargs)
    return original_run_sql(self, sql, **kwargs)

SqliteRunner.run_sql = safe_run_sql

# --- LIFESPAN AUTO-SEEDING ---
# --- LIFESPAN AUTO-SEEDING ---
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
        await asyncio.sleep(3) # <--- ADD THIS LINE: This pauses for 3 seconds so Google doesn't block you!
        
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
    chart_json = None
    summary_text = ""
    
    try:
        # THE FIX: Send the raw question! No confusing markdown instructions. 
        # Llama 3.3 will naturally pick up the tool and use it correctly.
        async for component in vanna_agent.send_message(request_context=context, message=request.question):
            comp_type = type(component).__name__
            
            if comp_type == 'StatusCardComponent' and getattr(component, 'status', '') == 'error':
                 return {"error": "Vanna Engine Error", "details": getattr(component, 'description', 'Check terminal.')}
            
            if hasattr(component, 'sql') and component.sql: generated_sql = component.sql
            elif hasattr(component, 'query') and component.query: generated_sql = component.query
            if hasattr(component, 'df') and component.df is not None: results_df = component.df
            if hasattr(component, 'plotly_json') and component.plotly_json: chart_json = component.plotly_json
                
            if comp_type not in ['StatusBarUpdateComponent', 'TaskTrackerUpdateComponent', 'ChatInputUpdateComponent']:
                if hasattr(component, 'text') and component.text: summary_text += component.text + " "
                elif hasattr(component, 'content') and component.content: summary_text += component.content + " "

        # The fallback stays quietly in the background just in case it forgets to use the tool
        if not generated_sql and summary_text:
            sql_match = re.search(r"```sql\s+(.*?)\s+```", summary_text, re.IGNORECASE | re.DOTALL)
            if not sql_match: sql_match = re.search(r"(SELECT\s+.*?(?:;|$))", summary_text, re.IGNORECASE | re.DOTALL)

            if sql_match:
                potential_sql = sql_match.group(1).strip()
                if is_sql_safe(potential_sql):
                    generated_sql = potential_sql
                    sql_tool = await vanna_agent.tool_registry.get_tool("run_sql")
                    if sql_tool:
                        runner_attr = 'sql_runner' if hasattr(sql_tool, 'sql_runner') else 'runner'
                        runner_instance = getattr(sql_tool, runner_attr)
                        results_df = await runner_instance.run_sql(sql=generated_sql)
                        summary_text = "I generated and executed this SQL query for you."

        if not generated_sql:
             return {"error": "The AI did not generate a SQL query.", "details": f"AI's raw output: {summary_text}"}

        return {
            "message": summary_text.strip() if summary_text else "Here are the database results:",
            "sql_query": generated_sql,
            "columns": list(results_df.columns) if results_df is not None else [],
            "rows": results_df.values.tolist() if results_df is not None else [],
            "row_count": len(results_df) if results_df is not None else 0,
            "chart": chart_json,
            "chart_type": "plotly" if chart_json else None
        }
        
    except Exception as e:
        return {"error": "FastAPI Crash.", "details": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)