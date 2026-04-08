import os
from dotenv import load_dotenv

# Vanna 2.0 Core Imports
from vanna import Agent, AgentConfig
from vanna.core.registry import ToolRegistry
from vanna.core.user import UserResolver, User, RequestContext

# Tools and Memory
from vanna.tools import RunSqlTool
from vanna.integrations.local.agent_memory import DemoAgentMemory

# Integrations
from vanna.integrations.openai import OpenAILlmService  
from vanna.integrations.sqlite import SqliteRunner

load_dotenv()

def setup_vanna_agent():
    # TRICK: Route to Groq's free servers
    os.environ["OPENAI_BASE_URL"] = "https://api.groq.com/openai/v1"
    
    # 1. Initialize the Service using Llama 3.3
    llm_service = OpenAILlmService(
        api_key=os.getenv("GROQ_API_KEY"), 
        model="llama-3.3-70b-versatile"  
    )

    # 2. Setup SQLite Runner
    sql_runner = SqliteRunner(database_path=os.getenv("DATABASE_PATH"))

    # 3. Setup Agent Memory (Kept here so main.py lifespan doesn't crash)
    agent_memory = DemoAgentMemory(max_items=1000)

    # 4. Create Tool Registry
    tools = ToolRegistry()
    
    # 5. THE FIX: ONLY REGISTER THE SQL TOOL. 
    # We are hiding VisualizeDataTool and MemoryTools from the AI so it doesn't crash Groq!
    tools.register_local_tool(
        RunSqlTool(sql_runner=sql_runner), 
        access_groups=['admin', 'user']
    )

    # 6. Simple User Resolver
    class SimpleUserResolver(UserResolver):
        async def resolve_user(self, request_context: RequestContext) -> User:
            return User(id="admin_user", name="Analyst", group_memberships=['admin', 'user'])

    # 7. Build the Final Agent
    return Agent(
        config=AgentConfig(),
        llm_service=llm_service,
        tool_registry=tools,
        user_resolver=SimpleUserResolver(),
        agent_memory=agent_memory
    )

# This instance is what other files will import
vanna_agent = setup_vanna_agent()