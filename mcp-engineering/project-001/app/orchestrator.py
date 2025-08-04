import os
import json
import asyncio
import logging
import re
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.stdio import stdio_client
import httpx

load_dotenv()

# Configurações
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
OPENROUTER_API_KEY = os.getenv("LLM_API_KEY")
MODEL = os.getenv("LLM_MODEL", "mistralai/mixtral-8x7b-instruct")

logger = logging.getLogger(__name__)

mcp_servers = {}

async def get_available_tools() -> list[str]:
    namespaces = ["github", "slack"]
    tools = []
    async with httpx.AsyncClient() as client:
        for ns in namespaces:
            resp = await client.get(f"http://localhost:8000/tools/{ns}")
            resp.raise_for_status()
            for tool in resp.json():
                tools.append(f"{ns}.{tool}")
    return tools

# 🆕 Novo parser robusto para JSON
def extract_json_from_text(text: str) -> dict:
    try:
        # Remove marcações Markdown e normaliza aspas
        cleaned = text.replace("\\_", "_").replace('\\"', '"').strip()

        # Extração por bloco ```json
        match = re.search(r"```json\n(.*?)```", cleaned, re.DOTALL)
        if match:
            json_part = match.group(1)
        else:
            json_part = cleaned

        # Força sanitização final
        json_part = json_part.strip().lstrip("`").rstrip("`")

        return json.loads(json_part)

    except Exception:
        raise ValueError(f"❌ Conteúdo inválido da LLM. Esperado JSON. Recebido:\n{text}")


async def call_openrouter(prompt: str) -> dict:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://app.cloud",
        "Content-Type": "application/json"
    }

    available_tools = await get_available_tools()
    tool_list = "\n".join(f"- {tool}" for tool in available_tools)

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a DevOps assistant. Based on the user's request, respond ONLY with a valid JSON object in this format:\n"
                    "{\"tool_name\": \"<namespace.tool_name>\", \"args\": { ... }}\n"
                    "DO NOT explain, just respond with valid JSON.\n"
                    f"Available tools:\n{tool_list}"
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.3
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()

async def run_tool_via_mcp(tool_name: str, args: dict, servers: dict):
    logger.info(f"🛠️ Tool solicitada: {tool_name}")
    namespace, tool = tool_name.split(".", 1)
    server = servers.get(namespace)
    if not server:
        raise ValueError(f"Namespace '{namespace}' não suportado ou MCP Server não inicializado.")
    logger.info(f"🔧 Executando: {tool_name} com args: {args}")
    return await server.call_tool(tool, args)

async def orchestrate(prompt: str, servers: dict):
    try:
        logger.info(f"📥 Prompt recebido: {prompt}")
        response = await call_openrouter(prompt)

        content = response["choices"][0]["message"]["content"]
        logger.info(f"📨 Resposta da LLM recebida com sucesso.")
        logger.info(f"📨 Resposta bruta da LLM:\n{content}")

        tool_request = extract_json_from_text(content)

        tool_name = tool_request["tool_name"]
        args = tool_request["args"]

        # Resposta direta sem execução de tool
        if "." not in tool_name or tool_name == "none":
            message = args.get("message") or "Desculpe, não entendi como posso ajudar ainda."
            return message

        logger.info(f"🛠️ Tool solicitada: {tool_name}")
        logger.info(f"🔧 Argumentos recebidos: {args}")

        # GitHub enrichment
        if tool_name == "github.create_branch" and "sha" not in args:
            if "repository" in args and "repo" not in args:
                args["repo"] = args.pop("repository")
            if "branch" not in args and "new_branch" in args:
                args["branch"] = args.pop("new_branch")

            owner = args.get("owner")
            repo = args.get("repo")
            base_branch = args.get("base")

            if owner and repo and base_branch:
                logger.info("🔍 Buscando SHA da branch base...")
                sha_response = await run_tool_via_mcp("github.list_branches", {"owner": owner, "repo": repo}, servers)

                def extract_branches(content):
                    try:
                        for entry in content:
                            if hasattr(entry, "text"):
                                parsed = json.loads(entry.text)
                                if "branches" in parsed:
                                    return parsed["branches"]
                    except Exception as e:
                        logger.error("❌ Erro ao extrair branches", exc_info=e)
                    return []

                branches = extract_branches(sha_response.content)
                logger.info(f"🔧 list de branches: {branches}")
                found = next((b for b in branches if b.get("name") == base_branch), None)

                if not found:
                    logger.warning(f"⚠️ Branch base '{base_branch}' não encontrada. Tentando usar a default_branch...")
                    repo_info = await run_tool_via_mcp("github.get_repository", {"owner": owner, "repo": repo}, servers)
                    default_branch = repo_info.content.get("default_branch")
                    if not default_branch:
                        raise ValueError("❌ Não foi possível determinar a default_branch do repositório.")
                    args["base"] = default_branch
                    found = next((b for b in branches if b.get("name") == default_branch), None)

                if found and found.get("commit") and found["commit"].get("sha"):
                    args["sha"] = found["commit"]["sha"]
                    logger.info(f"✅ SHA encontrado para '{args['base']}': {args['sha']}")
                else:
                    raise ValueError(f"❌ SHA não encontrado para a branch '{args['base']}' no repositório {owner}/{repo}")

        # Slack enrichment
        if tool_name.startswith("slack.") and "channel" in args and "channel_id" not in args:
            channel_name = args.pop("channel").lstrip("#")
            logger.info(f"🔍 Buscando ID para o canal '{channel_name}'...")

            channels_response = await run_tool_via_mcp("slack.slack_list_channels", {}, servers)
            raw_channels = channels_response.content
            slack_channels = []

            try:
                for entry in raw_channels:
                    if hasattr(entry, "text"):
                        decoded = json.loads(entry.text)
                        if "channels" in decoded:
                            slack_channels.extend(decoded["channels"])
            except Exception as e:
                raise ValueError(f"❌ Erro ao interpretar lista de canais Slack: {e}")

            found = next((c for c in slack_channels if c.get("name") == channel_name), None)

            if not found or not found.get("id"):
                raise ValueError(f"❌ Canal Slack '{channel_name}' não encontrado.")

            args["channel_id"] = found["id"]
            logger.info(f"✅ Canal '{channel_name}' resolvido para ID: {args['channel_id']}")

        return await run_tool_via_mcp(tool_name, args, servers)

    except json.JSONDecodeError as e:
        logger.error("❌ Erro ao decodificar JSON da resposta da LLM", exc_info=e)
        raise
    except Exception as e:
        logger.error("❌ Erro ao processar prompt", exc_info=e)
        raise
