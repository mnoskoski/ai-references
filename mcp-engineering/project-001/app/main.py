import asyncio
import json
import logging
import os
from contextlib import AsyncExitStack
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from orchestrator import orchestrate, run_tool_via_mcp

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

load_dotenv()

# MCP Registry
mcp_servers = {}

# FastAPI App
app = FastAPI(title="MCP Client")

# MCPServer Class
class MCPServer:
    def __init__(self, name: str, command: str, args: list[str], env: dict = None):
        self.name = name
        self.command = command
        self.args = args
        self.env = env or {}
        self.stack = AsyncExitStack()
        self.session: Optional[ClientSession] = None

    async def initialize(self):
        params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env={**os.environ, **self.env},
        )
        read, write = await self.stack.enter_async_context(stdio_client(params))
        self.session = await self.stack.enter_async_context(ClientSession(read, write))
        await self.session.initialize()
        logging.info(f"✅ MCP Server '{self.name}' inicializado com sucesso.")

    async def list_tools(self):
        if not self.session:
            raise RuntimeError("MCP session não inicializada.")
        resp = await self.session.list_tools()
        return [tool for kind, tools in resp if kind == "tools" for tool in tools]

    async def call_tool(self, name: str, args: dict):
        if not self.session:
            raise RuntimeError("MCP session não inicializada.")
        logging.info(f"🔧 Executando tool '{name}' com argumentos: {args}")
        return await self.session.call_tool(name, args)

    async def close(self):
        await self.stack.aclose()

# MCP Instances
github_mcp_server = MCPServer(
    name="github",
    command="node",
    args=["mcp-servers/build/index.js"],
    env={
        "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN", ""),
        "LOG_LEVEL": "debug",
        "SERVER_NAME": "github-mcp-server"
    }
)

#slack_mcp_server = MCPServer(
#    name="slack",
#    command="npx",
#    args=["-y", "@modelcontextprotocol/server-slack"],
#    env={
#        "SLACK_BOT_TOKEN": os.getenv("SLACK_BOT_TOKEN", ""),
#        "LOG_LEVEL": "debugssss",
#        "SLACK_TEAM_ID": os.getenv("SLACK_TEAM_ID", "")  # <- Corrigido de SLACK_TEAM_IDs
#    }
#)

# Models
class ToolRequest(BaseModel):
    tool_name: str
    args: dict

class PromptRequest(BaseModel):
    text: str

# Startup
@app.on_event("startup")
async def startup_event():
    await github_mcp_server.initialize()
    mcp_servers["github"] = github_mcp_server

    #await slack_mcp_server.initialize()
    #mcp_servers["slack"] = slack_mcp_server

# Shutdown
@app.on_event("shutdown")
async def shutdown_event():
    for server in mcp_servers.values():
        await server.close()

# Routes
@app.get("/")
async def root():
    #return {"message": "🚀 MCP Client online com GitHub e Slack MCP Servers"}
    return {"message": "🚀 MCP Client online com GitHub"}

@app.get("/tools/{provider}")
async def get_tools(provider: str):
    server = mcp_servers.get(provider)
    if not server:
        raise HTTPException(status_code=404, detail="MCP provider not found")
    tools = await server.list_tools()
    return [t.name for t in tools]

@app.post("/tools/{provider}/run")
async def run_tool(provider: str, req: ToolRequest):
    server = mcp_servers.get(provider)
    if not server:
        raise HTTPException(status_code=404, detail="MCP provider not found")
    try:
        result = await server.call_tool(req.tool_name, req.args)
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/orchestrate-text")
async def orchestrate_from_prompt(prompt: PromptRequest):
    try:
        logging.info(f"🧠 Prompt recebido: {prompt.text}")
        result = await orchestrate(prompt.text, servers=mcp_servers)
        return {"status": "ok", "result": result}
    except Exception as e:
        logging.exception("❌ Erro ao processar prompt")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/orchestrate")
async def orchestrate_from_explicit_tool(req: ToolRequest):
    try:
        logging.info(f"🧠 Execução direta: {req.tool_name} com args {req.args}")
        result = await run_tool_via_mcp(req.tool_name, req.args, mcp_servers)
        return {"status": "ok", "result": result}
    except Exception as e:
        logging.exception("❌ Erro ao executar tool diretamente")
        raise HTTPException(status_code=500, detail=str(e))

#from fastapi import Request
#
#@app.post("/slack/events")
#async def slack_events(request: Request):
#    payload = await request.json()
#
#    # ⚙️ Validação de URL do Slack (evento inicial de configuração)
#    if payload.get("type") == "url_verification":
#        return {"challenge": payload["challenge"]}
#
#    # 📦 Evento real do Slack
#    if payload.get("type") == "event_callback":
#        event = payload.get("event", {})
#
#        # Ignora mensagens do próprio bot
#        if event.get("type") == "message" and not event.get("bot_id"):
#            user_message = event.get("text", "").strip()
#            channel_id = event.get("channel")
#            thread_ts = event.get("ts")
#
#            # Remove menção ao bot se houver (ex: "<@U123> comando")
#            if user_message.startswith("<@"):
#                user_message = " ".join(user_message.split(" ")[1:]).strip()
#
#            try:
#                # 🔁 Gera resposta com LLM
#                result = await orchestrate(user_message, servers=mcp_servers)
#                response_text = result or "✅ Feito."
#            except Exception as e:
#                response_text = f"Erro ao processar: {e}"
#
#            # 📨 Responde no mesmo canal e thread
#            await run_tool_via_mcp("slack.slack_post_message", {
#                "channel_id": channel_id,
#                "text": response_text,
#                "thread_ts": thread_ts
#            }, servers=mcp_servers)
#
#    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
