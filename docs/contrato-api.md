# Contrato da API

Definido **antes** da implementação (contract-first). A coleção Postman em
[`postman/`](../postman) é a versão executável deste documento e é atualizada junto com a API.

- **Base URL (local):** `http://localhost:8000`
- **Formato:** JSON (`Content-Type: application/json`)
- **Autenticação:** `Authorization: Bearer <access_token>` nas rotas protegidas
- **Documentação interativa:** `GET /docs` (Swagger UI, gerado pelo FastAPI)

## Mapa das rotas

| Método | Rota | Auth | Fase | Descrição |
|---|---|:---:|:---:|---|
| `GET` | `/health` | — | 2 | Liveness check |
| `POST` | `/auth/register` | — | 2 | Cadastra um usuário |
| `POST` | `/auth/login` | — | 3 | Autentica e devolve o JWT |
| `GET` | `/auth/me` | ✅ | 3 | Dados do usuário autenticado |
| `PATCH` | `/users/me` | ✅ | 3 | Atualiza username e/ou senha |
| `DELETE` | `/users/me` | ✅ | 3 | Remove a própria conta |
| `POST` | `/chat` | ✅ | 6 | Envia pergunta ao LLM e devolve a resposta |
| `GET` | `/chat/history` | ✅ | 6 | Histórico de mensagens do usuário |

> O plano se refere às rotas como `POST /login` e `POST /chat`. `/login` está agrupada sob
> o prefixo `/auth` porque a Fase 3 acrescenta o CRUD de usuário, e separar
> *autenticação* de *gestão de usuário* mantém um router por responsabilidade.

---

## `GET /health`

Sem autenticação. Usado pelo healthcheck do Docker e pelo monitoramento do Render.

**200 OK**
```json
{ "status": "ok" }
```

---

## `POST /auth/register`

**Request**
```json
{ "username": "leonardo", "password": "senha-secreta-123" }
```

| Campo | Regra |
|---|---|
| `username` | obrigatório, 3–50 caracteres, `^[a-zA-Z0-9_.-]+$` |
| `password` | obrigatório, 8–128 caracteres |

**201 Created**
```json
{ "id": 1, "username": "leonardo", "created_at": "2026-09-16T03:12:45.123456Z" }
```

A resposta **nunca** inclui `password` nem `password_hash`.

| Erro | Quando |
|---|---|
| `409 Conflict` | `username` já existe |
| `422 Unprocessable Entity` | validação do Pydantic falhou |

---

## `POST /auth/login`

**Request**
```json
{ "username": "leonardo", "password": "senha-secreta-123" }
```

**200 OK**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

O token é **assinado, não criptografado**: qualquer pessoa consegue ler o payload, que é
apenas base64. Por isso ele carrega só o id do usuário e os prazos (`sub`, `iat`, `exp`) —
nada sensível. O que a assinatura garante não é sigilo, é que ninguém alterou o conteúdo.

Não há rota de logout: a sessão não tem estado no servidor, então um token emitido vale até
`exp`. Sair, na prática, é o cliente descartar o token. Revogação de verdade exigiria uma
lista de tokens invalidados no servidor — o que reintroduz o estado que o JWT existe para
evitar, e está fora do escopo deste projeto.

| Erro | Quando |
|---|---|
| `401 Unauthorized` | usuário inexistente **ou** senha errada |

> A mesma resposta 401 (`"Usuário ou senha inválidos"`) é usada nos dois casos, de
> propósito: distinguir "usuário não existe" de "senha errada" entrega ao atacante uma
> forma de enumerar contas válidas.

---

## `GET /auth/me` 🔒

**200 OK**
```json
{ "id": 1, "username": "leonardo", "created_at": "2026-09-16T03:12:45.123456Z" }
```

| Erro | Quando |
|---|---|
| `401 Unauthorized` | token ausente, malformado, expirado, com assinatura inválida, ou conta já removida |

---

## `PATCH /users/me` 🔒

Atualização parcial — envie apenas os campos que mudam.

**Request**
```json
{ "username": "leo", "password": "nova-senha-456" }
```

**200 OK** — mesmo formato de `GET /auth/me`.

| Erro | Quando |
|---|---|
| `401 Unauthorized` | token inválido |
| `409 Conflict` | novo `username` já em uso |
| `422 Unprocessable Entity` | validação falhou ou corpo vazio |

---

## `DELETE /users/me` 🔒

Remove a conta e, por cascata, todas as mensagens do usuário.

**204 No Content** — sem corpo.

---

## `POST /chat` 🔒

**Request**
```json
{ "message": "Explique o que é um cold start em uma frase." }
```

| Campo | Regra |
|---|---|
| `message` | obrigatório, 1–4000 caracteres, não pode ser só espaço em branco |

**200 OK**
```json
{
  "reply": "Cold start é a latência extra da primeira requisição...",
  "created_at": "2026-09-16T03:20:01.987654Z"
}
```

Efeito colateral: grava duas linhas em `messages` (`role='user'` e `role='assistant'`)
associadas ao usuário do token.

| Erro | Quando |
|---|---|
| `400 Bad Request` | a pergunta foi recusada pelo filtro de conteúdo do provedor |
| `401 Unauthorized` | token inválido |
| `422 Unprocessable Entity` | mensagem vazia, só espaços, ou acima de 4000 caracteres |
| `429 Too Many Requests` | rate limit por usuário excedido (Fase 8) |
| `502 Bad Gateway` | o provedor do LLM falhou ou respondeu fora do contrato |
| `503 Service Unavailable` | `GEMINI_API_KEY` não está configurada no servidor |
| `504 Gateway Timeout` | o provedor do LLM não respondeu no tempo limite |

Antes de devolver `502`, o backend tenta até 3 vezes em `429`, `500` e `503` — o provedor
devolve `503 "high demand"` com frequência no plano gratuito e a própria mensagem pede nova
tentativa. Timeout e erros permanentes (`400`, `401`, `403`, `404`) não são retentados.

O corpo de erro do provedor **nunca** é repassado ao cliente: ele vai para o log do servidor,
e a resposta HTTP traz uma mensagem genérica. Mensagens de erro de provedor costumam carregar
detalhes de infraestrutura — e, no pior caso, fragmentos da própria credencial.

Nada é gravado em `messages` quando a chamada ao LLM falha. Gravar a pergunta antes de ter a
resposta encheria o histórico de perguntas órfãs a cada falha do provedor.

> A chave da Gemini API vive só no backend, em variável de ambiente. O frontend chama
> `POST /chat` e não tem como alcançar o provedor diretamente.

---

## `GET /chat/history` 🔒

**Query params:** `limit` (1–200, default 50)

**200 OK**
```json
{
  "messages": [
    { "id": 1, "role": "user",      "content": "Explique cold start.", "created_at": "2026-09-16T03:20:00Z" },
    { "id": 2, "role": "assistant", "content": "Cold start é...",      "created_at": "2026-09-16T03:20:01Z" }
  ]
}
```

Retorna **apenas** as mensagens do usuário do token — o `user_id` vem do JWT, nunca do
corpo ou da query string, para que ninguém consiga ler o histórico de outra conta.

---

## Formato de erro

Todos os erros seguem o formato padrão do FastAPI:

```json
{ "detail": "Usuário ou senha inválidos" }
```

Para erros de validação (`422`), `detail` é a lista estruturada gerada pelo Pydantic,
apontando o campo e o motivo.
