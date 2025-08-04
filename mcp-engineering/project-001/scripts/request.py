import requests

url = "http://localhost:8000/tools/github/run"
payload = {
    "tool_name": "create_repository",
    "args": {
        "name": "poc-odemar",
        "private": False,
        "description": "Meu repositório criado via MCP"
    }
}
response = requests.post(url, json=payload)
print(response.json())