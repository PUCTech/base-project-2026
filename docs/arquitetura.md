# Arquitetura

## Visão de componentes

```mermaid
flowchart LR
    U([Usuário]) --> A

    subgraph Cliente
        A["Next.js (App Router)<br/>Vercel"]
    end

    subgraph Servidor
        B["FastAPI + Pydantic<br/>Render"]
    end

    A -->|"REST / JSON<br/>Bearer JWT"| B
    B -->|"SQLAlchemy ORM"| C[("PostgreSQL<br/>Supabase")]
    B -->|"HTTPS + API Key"| D["Gemini API<br/>Google AI Studio"]

    A -. "nunca acessa" .-> C
    A -. "nunca acessa" .-> D

    linkStyle 3,4 stroke:#d33,stroke-dasharray:4 4
```

A regra que sustenta o desenho: **o frontend não fala com o banco nem com o LLM**. Toda
credencial sensível — chave da Gemini, string de conexão do Postgres, segredo do JWT —
existe apenas como variável de ambiente no backend. Qualquer valor entregue ao navegador
deve ser tratado como público, porque é exatamente isso que ele é.

## Camadas do backend

```mermaid
flowchart TD
    R["routers/<br/>HTTP: rotas, status codes, dependências"]
    S["schemas/<br/>Pydantic: validação de entrada e forma da saída"]
    V["services/<br/>Regra de negócio: hash, JWT, chamada ao LLM"]
    M["models/<br/>SQLAlchemy: tabelas e relacionamentos"]
    DB[("PostgreSQL")]
    LLM["Gemini API"]

    R --> S
    R --> V
    V --> M
    M --> DB
    V --> LLM
```

| Camada | Responsabilidade | Não faz |
|---|---|---|
| `routers/` | Traduzir HTTP ↔ Python: rota, status code, autenticação | regra de negócio, SQL |
| `schemas/` | Validar a entrada e definir o formato da resposta | acesso a banco |
| `services/` | Hash de senha, emissão/validação de JWT, chamada ao LLM | conhecer `Request`/`Response` |
| `models/` | Mapear tabelas e relacionamentos | regra de negócio |

O ganho prático dessa separação: trocar o provedor de LLM mexe em um arquivo de
`services/`, e nenhum router, schema ou model precisa mudar.

## Fluxo de uma pergunta no chat

```mermaid
sequenceDiagram
    autonumber
    participant N as Next.js
    participant F as FastAPI
    participant P as PostgreSQL
    participant G as Gemini API

    N->>F: POST /chat  { message }  + Bearer JWT
    F->>F: valida JWT → user_id
    F->>F: valida corpo com Pydantic
    F->>G: generateContent  (API key no header x-goog-api-key)
    G-->>F: texto da resposta
    F->>P: INSERT messages ('user', message) + ('assistant', reply)
    F-->>N: 200  { reply, created_at }

    Note over F,P: A gravação vem depois da resposta:<br/>falha do provedor não deixa pergunta órfã.
    Note over N,G: O navegador nunca vê a API key<br/>nem a string de conexão do banco.
```

## Hospedagem gratuita — e o que cada escolha custa

| Serviço | Plataforma | Limitação relevante do plano free |
|---|---|---|
| Banco | Supabase | 500 MB; projeto pausa após ~1 semana sem atividade |
| Backend | Render | A instância **dorme** após ~15 min ociosa; a próxima requisição leva 30–60 s |
| Frontend | Vercel | Suficiente para o escopo; sem limitação prática aqui |

O Supabase resolve o banco, mas **não** hospeda a API: suas Edge Functions rodam em
Deno/TypeScript, não em Python. Daí o backend ficar no Render.

O cold start do Render não é um defeito a esconder — é o gancho para explicar, na
demonstração, por que a primeira requisição depois da ociosidade demora: o contêiner foi
desligado e precisa subir do zero. O frontend precisa lidar com isso (timeout generoso e
estado de carregamento honesto) em vez de fingir que a rede é sempre rápida.

---

# Assistente de cozinha

A branch `feature/cooking-idea` mantém o desenho acima e acrescenta um componente: o volume
onde ficam as fotos das receitas.

```mermaid
flowchart LR
    A["Next.js"] -->|"REST / JSON + JWT"| B["FastAPI"]
    A -->|"fotos: GET /media/..."| B
    B -->|"SQLAlchemy"| C[("PostgreSQL")]
    B -->|"HTTPS + API Key"| D["Gemini API"]
    B -->|"grava e serve"| E[("volume media-data<br/>fotos .webp")]
```

## Os serviços novos

| Módulo | Responsabilidade | Não sabe de |
|---|---|---|
| `services/ingredients.py` | Normalizar nomes, converter unidades, calcular o que falta | banco, HTTP |
| `services/pantry.py`, `shopping.py`, `recipes.py`, `recipe_social.py` | Regras de negócio de cada recurso | HTTP |
| `services/recipe_views.py` | Montar a resposta para quem vê: "tem X de Y", favorita, nota | HTTP |
| `services/storage.py` | Validar, reprocessar, gravar e apagar fotos | HTTP, banco |
| `services/kitchen_ai.py` | Contexto da cozinha, prompts e validação das respostas da IA | HTTP, formato da API do provedor |
| `services/llm.py` | Falar com o Gemini: chave, retentativa, histórico, JSON | cozinha |
| `routers/llm_errors.py` | Traduzir as falhas do LLM em status HTTP, igual para todas as rotas | — |

A fronteira entre `kitchen_ai.py` e `llm.py` é a mesma da `main`, agora sob mais carga: trocar
o Gemini por outro provedor continua mexendo só em `llm.py`, embora agora existam quatro
funcionalidades de IA em vez de uma.

## Chat com o contexto da cozinha

```mermaid
sequenceDiagram
    autonumber
    participant N as Next.js
    participant F as FastAPI
    participant P as PostgreSQL
    participant G as Gemini API

    N->>F: POST /chat { message } + Bearer JWT
    F->>P: despensa, lista de compras, favoritas, últimas 10 falas
    F->>F: monta a instrução de sistema<br/>(dados delimitados e declarados como dados)
    F->>G: systemInstruction + histórico + pergunta
    G-->>F: resposta
    F->>P: INSERT messages (pergunta e resposta)
    F-->>N: 200 { reply }

    Note over N,F: O contexto é montado no servidor, a partir do banco:<br/>o navegador não tem como enviar uma despensa forjada.
```

## A IA propõe, a pessoa decide

```mermaid
sequenceDiagram
    autonumber
    actor U as Pessoa
    participant N as Next.js
    participant F as FastAPI
    participant G as Gemini API
    participant P as PostgreSQL

    U->>N: "um jantar rápido"
    N->>F: POST /ai/recipe-draft
    F->>G: pedido + despensa + responseSchema
    G-->>F: JSON
    F->>F: valida com RecipeIn<br/>(o mesmo schema de quem digita)
    F-->>N: rascunho
    Note over F,P: Nada foi gravado até aqui.
    N->>U: formulário preenchido
    U->>N: revisa, corrige, salva
    N->>F: POST /recipes
    F->>P: INSERT
```

O mesmo padrão vale para o cadastro rápido da despensa (`/ai/pantry-parse` → revisão →
`POST /pantry/batch`) e para as sugestões de compra (`/ai/shopping-suggestions` → escolha →
`POST /shopping-list`).
