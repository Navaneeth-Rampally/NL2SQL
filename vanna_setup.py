import os
from dotenv import load_dotenv

# Vanna 2.0 Core Imports
from vanna import Agent, AgentConfig
from vanna.core.registry import ToolRegistry
from vanna.core.user import UserResolver, User, RequestContext
from vanna.integrations.local.agent_memory import DemoAgentMemory
from vanna.tools import RunSqlTool

# The Official Ollama Integration
from vanna.integrations.ollama import OllamaLlmService
from vanna.integrations.sqlite import SqliteRunner

load_dotenv()

def setup_vanna_agent():
    # 1. Initialize Ollama Service (Running locally on your machine!)
    llm_service = OllamaLlmService(
        model="llama3.2", 
    )

    # 2. Setup SQLite Runner
    sql_runner = SqliteRunner(database_path=os.getenv("DATABASE_PATH"))

    # 3. Setup Agent Memory 
    agent_memory = DemoAgentMemory(max_items=1000)

    # 4. Create Tool Registry
    tools = ToolRegistry()
    
    # 5. Register ONLY the SQL tool for maximum stability
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

vanna_agent = setup_vanna_agent()