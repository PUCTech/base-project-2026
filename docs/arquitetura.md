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
    F->>P: INSERT messages (user_id, 'user', message)
    F->>G: generateContent  (API key do ambiente)
    G-->>F: texto da resposta
    F->>P: INSERT messages (user_id, 'assistant', reply)
    F-->>N: 200  { reply, created_at }

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
