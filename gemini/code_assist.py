# code_assist.py
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente do .env
load_dotenv()

from typing import TypedDict, Annotated, List, Union
import operator
from pathlib import Path
import json
import re # Importar regex para extrair blocos de código

# Usando o conector do Google Gemini
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage

# LangGraph para a orquestração
from langgraph.graph import StateGraph, END
import yaml # Importar PyYAML para parsear YAML

# LangGraph para a orquestração
from langgraph.graph import StateGraph, END
import yaml # Importar PyYAML para parsear YAML


# --- NOVO: Importações para RAG ---
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter


# --- NOVO: Configuração do Retriever (Base de Conhecimento) ---
print("Configurando a base de conhecimento (RAG)...")
# 1. Carregar os embeddings do Google
embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")

# 2. Carregar os documentos da pasta knowledge_base
loader = DirectoryLoader(
    "./knowledge_base/",
    glob="**/*.md", # Carrega todos os arquivos markdown
    loader_cls=TextLoader,
    loader_kwargs={"encoding": "utf-8"},
    show_progress=True,
    use_multithreading=True
)
documents = loader.load()

# 3. Dividir os documentos em pedaços menores (chunks)
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
docs = text_splitter.split_documents(documents)

# 4. Criar o VectorStore com FAISS e o Retriever
# Isso cria um índice local dos seus documentos para busca rápida
vector_store = FAISS.from_documents(docs, embeddings)
retriever = vector_store.as_retriever(search_kwargs={"k": 3}) # Retorna os 3 chunks mais relevantes

print("Base de conhecimento pronta.")


print("digite 'sair' para sair do assistente de código.")

while True:
    user_input = input("Você: ")
    if user_input.lower() == 'sair':
        print("Saindo do assistente de código. Até logo!")
        break

    # Chama a função principal com o input do usuário
    run_code_assistant(user_input)
# --- 1. Definir as Ferramentas (Tools) ---

# --- NOVO: Ferramenta para consultar a base de conhecimento ---
@tool
def consult_knowledge_base(query: str) -> str:
    """Consulta a base de conhecimento interna para encontrar padrões de desenvolvimento, exemplos de código e convenções.
    Use esta ferramenta PRIMEIRO para qualquer tarefa que envolva a criação de código ou arquivos de projeto (Terraform, Docker, etc.)
    para garantir que os padrões da empresa sejam seguidos. A entrada deve ser uma pergunta clara sobre o que você está procurando.
    Exemplo: 'qual o padrão para criar um bucket S3 no terraform?'
    """
    print(f"DEBUG: Consultando a base de conhecimento com a query: '{query}'")
    retrieved_docs = retriever.invoke(query)
    # Formata a saída para ser facilmente compreendida pela LLM
    context = "\n\n---\n\n".join([doc.page_content for doc in retrieved_docs])
    if not context:
        return "Nenhuma informação relevante encontrada na base de conhecimento."
    return f"Informação relevante encontrada na base de conhecimento:\n\n{context}"

@tool
def create_directory(directory_path: str) -> str:
    """Cria um novo diretório no sistema de arquivos.
    Use esta ferramenta quando precisar criar uma pasta para organizar arquivos.
    A entrada deve ser o caminho completo do diretório, por exemplo, 'my_project/backend'.
    """
    try:
        Path(directory_path).mkdir(parents=True, exist_ok=True)
        return f"Diretório '{directory_path}' criado com sucesso."
    except Exception as e:
        return f"Erro ao criar diretório '{directory_path}': {e}"

@tool
def write_file(file_path: str, content: str) -> str:
    """Escreve o conteúdo especificado em um arquivo no caminho dado.
    Use esta ferramenta para criar ou atualizar arquivos como Dockerfile, .env, README.md, etc.
    A entrada deve ser o caminho completo do arquivo e o conteúdo a ser escrito.
    """
    try:
        # Garante que o diretório pai exista antes de escrever o arquivo
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w") as f:
            f.write(content)
        return f"Arquivo '{file_path}' escrito com sucesso."
    except Exception as e:
        return f"Erro ao escrever no arquivo '{file_path}': {e}"
    

@tool
def read_file(file_path: str) -> str:
    """Lê o conteúdo de um arquivo específico e o retorna como uma string.
    Use esta ferramenta quando precisar analisar o conteúdo de um script, arquivo de configuração, etc.
    A entrada deve ser o caminho completo do arquivo, por exemplo, 'my_project/backend/app.py'.
    """
    try:
        if not Path(file_path).is_file():
            return f"Erro: O caminho '{file_path}' não é um arquivo ou não existe."
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return f"Conteúdo de '{file_path}':\n```\n{content}\n```"
    except Exception as e:
        return f"Erro ao ler arquivo '{file_path}': {e}"

@tool
def list_directory_contents(directory_path: str) -> str:
    """Lista o conteúdo de um diretório (arquivos e subdiretórios) e retorna uma string formatada.
    Use esta ferramenta para entender a estrutura de um diretório ou para encontrar arquivos específicos.
    A entrada deve ser o caminho completo do diretório, por exemplo, 'my_project/backend'.
    """
    try:
        if not Path(directory_path).is_dir():
            return f"Erro: O caminho '{directory_path}' não é um diretório ou não existe."
        
        contents = os.listdir(directory_path)
        if not contents:
            return f"Diretório '{directory_path}' está vazio."
        
        items = []
        for item in contents:
            item_path = Path(directory_path) / item
            if item_path.is_file():
                items.append(f"  - Arquivo: {item}")
            elif item_path.is_dir():
                items.append(f"  - Diretório: {item}/")
        
        return f"Conteúdo do diretório '{directory_path}':\n" + "\n".join(items)
    except Exception as e:
        return f"Erro ao listar diretório '{directory_path}': {e}"

# --- 2. Definir o LLM e vincular as ferramentas ---
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)
llm_with_tools = llm.bind_tools([create_directory, write_file, read_file, list_directory_contents])


# --- 3. Definir o Estado do Grafo ---
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]

# --- 4. Definir os Nós (Nodes) ---

# Mapeamento de nomes de ferramentas para as funções reais
TOOL_MAP = {
    "create_directory": create_directory,
    "write_file": write_file,
    "read_file": read_file,
    "list_directory_contents": list_directory_contents,
}

def call_llm(state: AgentState):
    messages = state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

def call_tool(state: AgentState):
    messages = state["messages"]
    last_message = messages[-1]
    
    tool_results = []
    actual_tool_calls = [] # Esta lista conterá os dicionários de chamadas de ferramenta a serem executadas

    # Tenta obter tool_calls diretamente do atributo (como LangChain espera)
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        print("DEBUG: LLM gerou tool_calls no atributo nativo.")
        # Se veio no atributo, geralmente já está parseado corretamente
        for tc in last_message.tool_calls:
            # Garante que seja um dicionário compatível ou converte se for objeto
            if isinstance(tc, dict):
                actual_tool_calls.append(tc)
            else: # Assumindo LangChain ToolCall object
                actual_tool_calls.append({'name': tc.name, 'arguments': tc.args, 'id': tc.id})
    elif isinstance(last_message, AIMessage) and last_message.content:
        # Se não há tool_calls diretos, tenta extrair de um bloco de código YAML/JSON no conteúdo
        print("DEBUG: LLM não gerou tool_calls no atributo nativo, tentando extrair do conteúdo.")
        # Regex para encontrar blocos de código YAML ou JSON
        match = re.search(r"```(?:yaml|json)\s*\n(.*?)```", last_message.content, re.DOTALL)
        if match:
            code_block = match.group(1)
            try:
                # Tenta carregar como YAML primeiro, pois JSON é um subset de YAML
                parsed_content = yaml.safe_load(code_block)
                if isinstance(parsed_content, dict) and 'tool_calls' in parsed_content:
                    actual_tool_calls = parsed_content['tool_calls']
                    print(f"DEBUG: Extraído tool_calls do conteúdo YAML/JSON: {actual_tool_calls}")
                else:
                    print(f"ATENÇÃO: Conteúdo do bloco de código não possui 'tool_calls' no formato esperado: {parsed_content}")
            except (yaml.YAMLError, json.JSONDecodeError) as e:
                print(f"ERRO DE PARSING: Não foi possível parsear o bloco de código como YAML/JSON: {e}")
                # Aqui o LLM falhou em formatar o bloco de código corretamente.
                # A próxima mensagem para o LLM deveria ser um erro de parsing.
        else:
            print("DEBUG: Não foi encontrado bloco de código de ferramenta no conteúdo do LLM.")


    if not actual_tool_calls:
        print("DEBUG: Nenhuma chamada de ferramenta válida para executar.")
        # Se o LLM não gerou tool_calls diretos E não gerou um bloco de código,
        # e a should_continue decidiu vir pra cá, significa um problema.
        # Precisamos de uma ToolMessage de erro ou algo para feedback.
        tool_results.append(ToolMessage(tool_name="system_error", content="Nenhuma chamada de ferramenta detectada ou formatada incorretamente para execução.", tool_call_id=""))
        return {"messages": tool_results}

    for tool_call_info in actual_tool_calls:
        tool_name = tool_call_info.get('name')
        tool_args = tool_call_info.get('arguments', {}) # Assegura que tool_args seja um dict, mesmo se ausente
        tool_call_id = tool_call_info.get('id', '') # Pode não haver ID se parseado do texto

        if not isinstance(tool_args, dict):
            print(f"ATENÇÃO: Arguments da ferramenta '{tool_name}' não é um dicionário após parsing: {tool_args}. Usando dict vazio.")
            tool_args = {}

        if not tool_name:
            print(f"ATENÇÃO: Não foi possível determinar o nome da ferramenta para {tool_call_info}. Pulando.")
            tool_results.append(ToolMessage(tool_name="unknown", content=f"Não foi possível determinar o nome da ferramenta para: {tool_call_info}", tool_call_id=tool_call_id))
            continue

        if tool_name not in TOOL_MAP:
            result_content = f"Erro: Ferramenta desconhecida '{tool_name}'."
            tool_results.append(ToolMessage(tool_name=tool_name, content=result_content, tool_call_id=tool_call_id))
            continue

        try:
            tool_function = TOOL_MAP[tool_name]
            result_content = tool_function.invoke(tool_args)
            
            tool_results.append(ToolMessage(tool_name=tool_name, content=str(result_content), tool_call_id=tool_call_id))

        except Exception as e:
            error_message = f"Erro ao executar a ferramenta '{tool_name}' com argumentos {tool_args}: {e}"
            print(f"ERRO DE FERRAMENTA: {error_message}")
            tool_results.append(ToolMessage(tool_name=tool_name, content=error_message, tool_call_id=tool_call_id))
    
    return {"messages": tool_results}

# --- 5. Definir a Lógica Condicional (Edge) ---
def should_continue(state: AgentState):
    messages = state["messages"]
    last_message = messages[-1]
    
    # Se a última mensagem é uma mensagem do LLM e contém tool_calls no atributo (padrão LangChain)
    if isinstance(last_message, AIMessage) and hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        print("DEBUG: LLM quer chamar uma ferramenta (via atributo tool_calls).")
        return "call_tool"
    # OU se é uma AIMessage com conteúdo que POSSIVELMENTE contém tool_calls em um bloco de código
    elif isinstance(last_message, AIMessage) and last_message.content and re.search(r"```(?:yaml|json)\s*\n(.*?)```", last_message.content, re.DOTALL):
        print("DEBUG: LLM quer chamar uma ferramenta (via bloco de código no conteúdo).")
        return "call_tool"
    # Se a última mensagem é o resultado de uma ToolMessage, o LLM precisa processá-lo e então parar
    # OU se é uma AIMessage sem tool_calls e sem bloco de código, significa que o LLM já tem uma resposta final.
    elif isinstance(last_message, ToolMessage) or (isinstance(last_message, AIMessage) and not last_message.tool_calls and not re.search(r"```(?:yaml|json)\s*\n(.*?)```", last_message.content, re.DOTALL)):
        print("DEBUG: LLM tem a resposta final ou o fluxo terminou após tool_node.")
        return "end" # Sinaliza que o fluxo deve terminar
    
    # Caso de fallback, embora com LLM e Tools bem definidos, não deve acontecer muito
    print("DEBUG: Estado indefinido, terminando o fluxo.")
    return "end"


# --- 6. Construir o Grafo ---
workflow = StateGraph(AgentState)

workflow.add_node("llm_node", call_llm)
workflow.add_node("tool_node", call_tool)

workflow.set_entry_point("llm_node")

workflow.add_conditional_edges(
    "llm_node", 
    should_continue, 
    {
        "call_tool": "tool_node", 
        "end": END               
    }
)


workflow.add_edge('tool_node', 'llm_node') # Sempre retorna para o LLM para processar o resultado da ferramenta

app = workflow.compile()

# --- 7. Função Principal para Usar o Assistente ---
def run_code_assistant(prompt: str):
    print(f"\n--- Assistente de Código ---")
    print(f"Comando recebido: {prompt}")
    
    system_prompt_content = (
        "Você é um assistente de código altamente competente e autônomo. "
        "Quando perguntarem teu nome é Marcelinho"
        "Seu objetivo principal é ajudar o usuário a criar, gerenciar, LER e ANALISAR estruturas de projeto (diretórios e arquivos) "
        "e a gerar ou interpretar conteúdo de código para esses arquivos (como Dockerfiles, Terraform, scripts Python, etc.).\n\n"
        "Você tem acesso e **DEVE usar** as seguintes ferramentas:\n"
        "- `create_directory(directory_path: str)`: Cria um novo diretório. **EXIGE o caminho completo.**\n"
        "- `write_file(file_path: str, content: str)`: Escreve conteúdo em um arquivo. **EXIGE o caminho e o conteúdo.**\n"
        "- `read_file(file_path: str)`: Lê o conteúdo de um arquivo. **EXIGE o caminho completo do arquivo.**\n" # NOVA
        "- `list_directory_contents(directory_path: str)`: Lista arquivos e subdiretórios em um diretório. **EXIGE o caminho completo do diretório.**\n\n" # NOVA
        "**Diretrizes CRUCIAIS para gerar chamadas de ferramentas:**\n"
        "1.  **Gere APENAS a chamada da ferramenta em formato YAML/JSON, DENTRO de um bloco de código YAML/JSON.** Comece o bloco com ```yaml ou ```json e termine com ```. \n"
        "    - **NÃO adicione texto extra fora do bloco de código** ao chamar ferramentas. O texto livre deve ser usado APENAS para a resposta final após todas as ferramentas serem executadas.\n"
        "    - **EXEMPLO para `create_directory`:**\n"
        "      ```yaml\n"
        "      tool_calls:\n"
        "        - name: create_directory\n"
        "          arguments:\n"
        "            directory_path: meu_nginx_app\n"
        "      ```\n"
        "    - **EXEMPLO para `write_file` (gerar Dockerfile):**\n"
        "      ```yaml\n"
        "      tool_calls:\n"
        "        - name: write_file\n"
        "          arguments:\n"
        "            file_path: meu_nginx_app/Dockerfile\n"
        "            content: |\n"
        "              FROM nginx:latest\n"
        "              COPY ./html /usr/share/nginx/html\n"
        "      ```\n"
        "    - **EXEMPLO para `read_file`:**\n" # NOVO EXEMPLO
        "      ```yaml\n"
        "      tool_calls:\n"
        "        - name: read_file\n"
        "          arguments:\n"
        "            file_path: meu_projeto/main.py\n"
        "      ```\n"
        "    - **EXEMPLO para `list_directory_contents`:**\n" # NOVO EXEMPLO
        "      ```yaml\n"
        "      tool_calls:\n"
        "        - name: list_directory_contents\n"
        "          arguments:\n"
        "            directory_path: /projetos/minha_app\n"
        "      ```\n"
        "2.  **Planejamento e Ordem:**\n"
        "    - **Priorize a criação de diretórios antes de arquivos dentro deles.** Se o diretório não existir, a escrita do arquivo falhará.\n"
        "    - Se o usuário pedir para analisar um diretório ou arquivo, comece com a ferramenta apropriada (`list_directory_contents` ou `read_file`).\n" # Adição
        "    - Se o usuário não especificar um nome de diretório (ex: 'no meu diretório'), você DEVE criar um nome de diretório padrão lógico (ex: 'nginx-app', 'terraform-project', 'my-code').\n"
        "    - Construa o `file_path` completo, incluindo o nome do diretório que você criou ou o caminho completo fornecido pelo usuário.\n"
        "3.  **Geração de Conteúdo (para escrita) e Análise (para leitura):**\n" # Modificação
        "    - Para arquivos de código (Dockerfile, Terraform, etc.) que precisam ser escritos, gere o **conteúdo COMPLETO e correto** do arquivo dentro do argumento `content`.\n"
        "    - Ao receber o conteúdo de um arquivo ou a lista de um diretório, ANALISE cuidadosamente a informação e forneça uma explicação CLARA e CONCISA do que foi encontrado ou do que os scripts estão fazendo. Responda em linguagem natural após a análise.\n" # NOVO
        "4.  **Resposta Final:** Após a execução BEM-SUCEDIDA de **todas as ferramentas necessárias**, forneça uma resposta final amigável ao usuário, confirmando o que foi feito (criado, lido, analisado) e onde. Não repita os detalhes técnicos das chamadas de ferramentas. **Não gere texto livre ou confirmações ANTES de executar as ferramentas.** Se houver falha (você receberá uma `ToolMessage` de erro), analise o erro e explique de forma concisa como corrigir ou o que deu errado.\n"
        "5.  **Mantenha a conversa focada na criação, gerenciamento, leitura e análise de arquivos/diretórios.**\n\n"
        "Vamos começar! Qual diretório ou arquivo você gostaria de criar, ler ou analisar?"
    )
    
    # Inicia a conversa com a mensagem do usuário, incluindo o SystemMessage
    initial_state = {"messages": [SystemMessage(content=system_prompt_content), HumanMessage(content=prompt)]}
    
    # Invoca o agente
    final_state = app.invoke(initial_state) 
    
    # A última mensagem no estado final é a resposta que queremos exibir
    final_response_message = final_state["messages"][-1]
    
    # Garante que estamos pegando o conteúdo da mensagem final do LLM
    if isinstance(final_response_message, AIMessage):
        print("\nAssistente respondeu:")
        print(final_response_message.content)
    elif isinstance(final_response_message, ToolMessage):
        print("\nAssistente executou a ferramenta e retornou:")
        print(final_response_message.content)
        print("\nNota: O LLM pode precisar de um prompt mais direcionado para gerar uma resposta final amigável após a execução da ferramenta.")
    else:
        print("\nResposta final inesperada:")
        print(str(final_response_message))

    print("-" * 30)

# --- 8. Execução via Linha de Comando ---
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Uso: python code_assist.py <seu comando para o assistente>")
        print("Exemplo: python code_assist.py criar uma folder 'my_app' com um Dockerfile de um nginx que sobe a app na porta 8080")
        sys.exit(1)
    
    user_prompt = " ".join(sys.argv[1:])
    
    run_code_assistant(user_prompt)