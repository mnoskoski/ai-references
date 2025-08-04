# 🧠 MCP AI

[![Docker](https://img.shields.io/badge/docker-ready-blue)](https://hub.docker.com/) [![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

**MCP AI** é uma plataforma inteligente que automatiza o **provisionamento de infraestrutura** diretamente no GitHub, utilizando o protocolo **Model Copilot Protocol (MCP)**. O projeto permite a criação e o gerenciamento de repositórios, branches, pull requests e outras operações complexas de forma programática ou via chatbot.

## ✨ Visão Geral

Este projeto é uma aplicação **backend** desenvolvida em **FastAPI** que atua como um cliente MCP. Ele se conecta a servidores MCP (como o [GitHub MCP Server](https://github.com/github/github-mcp-server)) para executar ações automatizadas.

Futuramente, a plataforma será expandida para incluir uma **interface de usuário (frontend)** completa, permitindo a criação e o gerenciamento de recursos de infraestrutura com base em prompts de texto, transformando-o em um produto **SaaS (Software as a Service)**.

---

## 🚀 Funcionalidades Principais

* **Automação com MCP**: Integração total com o [GitHub MCP Server](https://github.com/github/github-mcp-server) para automação de tarefas.
* **API RESTful**: Uma API simples para listar e executar as ferramentas MCP disponíveis.
* **Gestão de Projetos**: Cria automaticamente **issues do GitHub** e **cards de projeto** a partir do seu `ROADMAP.md`.
* **Pronto para Contêineres**: Configuração completa com **Docker Compose** para um ambiente de desenvolvimento e produção rápido.
* **Expansível**: Projetado para futuras integrações com **Slack**, e-mail e uma interface de usuário dedicada.

---

## ⚙️ Configuração e Instalação (Ambiente Local)

Para começar a utilizar o MCP AI, siga estes passos simples:

### 1. Clonar o Repositório

``` bash
git clone [https://github.com/mnoskoski/ai-references.git](https://github.com/mnoskoski/ai-references.git)
cd mcp-engineering/project-001
```

### 2. Configurar Variáveis de Ambiente
Crie um arquivo .env na raiz do projeto com as seguintes variáveis.

Importante: Substitua ghp_your_github_token pelo seu Personal Access Token do GitHub.

``` bash
GITHUB_TOKEN=ghp_your_github_token
LOG_LEVEL=info
SERVER_NAME=mcp-server
```
### 3. Executar com Docker Compose
Inicie a aplicação e o servidor MCP com um único comando:

``` bash
docker compose up --build
```

# 🛠️ Endpoints da API
A aplicação oferece os seguintes endpoints para interação via API:

Método	Rota	Descrição
GET	/tools	Lista todas as ferramentas MCP disponíveis
POST	/tools/run	Executa uma ferramenta MCP específica
GET	/.well-known/copilot-mcp.json	Manifest MCP para integração com o GitHub

# Exportar para as Planilhas
📦 Exemplo de Uso da API
Para executar uma ferramenta MCP, envie uma requisição POST para o endpoint /tools/run com o seguinte formato:

```bash
POST /tools/run

{
  "tool_name": "create_repository",
  "args": {
    "name": "infra-demo",
    "private": true
  }
}
```

# 🖼️ Arquitetura do Sistema
```
FastAPI MCP Client ─┬─> GitHub MCP Server (Node.js)
                    └─> (futuro) Slack Bot, Agente de E-mail, Frontend em React
```

# 💡Idéias 
- GitHub MCP
- github-mcp-server