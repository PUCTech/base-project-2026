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
| `DELETE` | `/chat/history` | ✅ | cozinha | Apaga o histórico (conversa nova) |

As rotas do assistente de cozinha — despensa, receitas, lista de compras e IA — estão em
[Assistente de cozinha](#assistente-de-cozinha), no fim deste documento.

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
| `429 Too Many Requests` | a cota de uso do provedor acabou por ora; o header `Retry-After` diz quantos segundos esperar |
| `502 Bad Gateway` | o provedor do LLM falhou ou respondeu fora do contrato |
| `503 Service Unavailable` | `GEMINI_API_KEY` não está configurada no servidor |
| `504 Gateway Timeout` | o provedor do LLM não respondeu no tempo limite |

Antes de devolver `502`, o backend tenta até 3 vezes em `429`, `500` e `503` — o provedor
devolve `503 "high demand"` com frequência no plano gratuito e a própria mensagem pede nova
tentativa. Timeout e erros permanentes (`400`, `401`, `403`, `404`) não são retentados.

O `429` do provedor é tratado à parte: o Gemini informa no corpo da resposta (`RetryInfo`)
quanto esperar. Se a espera for curta, o backend espera e tenta de novo; se for longa (mais de
10 s), ele não prende a requisição — responde `429` na hora, com `Retry-After`, e a tela mostra
quanto falta.

Na branch do assistente de cozinha, o modelo recebe também o contexto da cozinha do usuário
(despensa, lista de compras, receitas favoritas) como instrução de sistema, e as últimas 10
falas como histórico. O corpo da requisição não muda: esse contexto é montado no servidor, a
partir do banco, e o navegador não tem como forjá-lo.

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

---

# Assistente de cozinha

Rotas da branch `feature/cooking-idea`. Todas exigem o token (🔒). As de **despensa** e **lista
de compras** são privadas: um id de outra conta responde `404`, e não `403`, para não confirmar
que ele existe. As de **receitas** são públicas para leitura; alterar a receita de outra pessoa
responde `403` — a existência dela não é segredo, o que falta é permissão.

## Mapa das rotas

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/pantry` | Lista a despensa, por categoria e nome |
| `POST` | `/pantry` | Adiciona um item (`409` se o ingrediente já existe) |
| `POST` | `/pantry/batch` | Adiciona vários, **somando** aos que já existem |
| `PATCH` | `/pantry/{id}` | Atualização parcial; `null` explícito apaga o valor |
| `DELETE` | `/pantry/{id}` | Remove um item |
| `GET` | `/recipes` | Lista receitas (`scope`, `q`, `limit`, `offset`) |
| `POST` | `/recipes` | Cria uma receita |
| `GET` | `/recipes/{id}` | Detalhe, com ingredientes marcados pela despensa de quem vê |
| `PUT` | `/recipes/{id}` | Substitui a receita inteira (só o autor) |
| `DELETE` | `/recipes/{id}` | Remove a receita e a foto (só o autor) |
| `GET` | `/recipes/{id}/missing-ingredients` | O que falta na despensa, e quanto |
| `PUT` / `DELETE` | `/recipes/{id}/image` | Envia ou remove a foto (só o autor) |
| `PUT` / `DELETE` | `/recipes/{id}/favorite` | Favorita ou desfavorita (idempotente) |
| `PUT` / `DELETE` | `/recipes/{id}/rating` | Dá, troca ou remove a própria nota |
| `GET` / `POST` | `/recipes/{id}/comments` | Lista ou cria comentários |
| `DELETE` | `/recipes/{id}/comments/{comment_id}` | Remove (autor do comentário ou da receita) |
| `GET` | `/shopping-list` | Lista de compras: não comprados primeiro, por categoria |
| `POST` | `/shopping-list` | Adiciona itens, somando aos repetidos |
| `POST` | `/shopping-list/from-recipe/{id}` | Adiciona o que falta para a receita (`servings` opcional) |
| `POST` | `/shopping-list/checkout` | Leva os marcados para a despensa |
| `DELETE` | `/shopping-list/checked` | Descarta os marcados sem levar à despensa |
| `PATCH` | `/shopping-list/{id}` | Atualiza ou marca um item |
| `DELETE` | `/shopping-list/{id}` | Remove um item |
| `POST` | `/ai/recipe-draft` | Rascunho de receita para revisar |
| `POST` | `/ai/pantry-parse` | Interpreta texto livre como itens da despensa |
| `POST` | `/ai/shopping-suggestions` | Sugere compras, com o motivo de cada item |
| `GET` | `/media/recipes/{arquivo}` | Foto de receita (pública, sem token) |

## Tipos compartilhados

| Campo | Regra |
|---|---|
| `name` (ingrediente, item) | 1–100 caracteres, espaços nas pontas removidos |
| `quantity` | opcional; na despensa ≥ 0 (zero = "acabou"), nos demais > 0; até 100 000 |
| `unit` | opcional, até 20 caracteres; `""` vira `null` |
| `category` | `hortifruti`, `carnes`, `laticinios`, `graos`, `padaria`, `temperos`, `doces`, `bebidas`, `congelados`, `outros` |
| `difficulty` | `facil`, `media`, `dificil` |

Nomes são comparados pela forma normalizada: "Tomates", "tomate" e "TOMATE" são o mesmo
ingrediente, assim como "Açúcar" e "acucar".

## Despensa

**`POST /pantry`**
```json
{ "name": "Arroz", "quantity": 2, "unit": "kg", "category": "graos", "expires_on": "2026-12-01" }
```

**201 Created**
```json
{
  "id": 1, "name": "Arroz", "quantity": 2.0, "unit": "kg", "category": "graos",
  "expires_on": "2026-12-01", "created_at": "...", "updated_at": "..."
}
```

`quantity: null` significa "tenho, mas não controlo quanto" (sal, azeite); `0` significa
"acabou" — o item fica para lembrar de comprar.

**`POST /pantry/batch`** recebe `{ "items": [ ... ] }` (1–100 itens) e devolve os itens
afetados. Ingrediente que já existe **soma** em vez de dar `409`, convertendo unidades da mesma
grandeza (2 kg + 500 g = 2,5 kg). Unidades incomparáveis (3 un + 500 g) deixam a quantidade como
`null`, em vez de inventar um total. Fica a validade mais próxima. Tudo ou nada: um item
inválido barra o lote inteiro.

| Erro | Quando |
|---|---|
| `404 Not Found` | o item não existe ou é de outra conta |
| `409 Conflict` | já existe um item com esse nome na despensa (`POST` e `PATCH`) |
| `422 Unprocessable Entity` | validação falhou, ou `PATCH` vazio |

## Receitas

**`POST /recipes`** (e `PUT /recipes/{id}`, com o mesmo corpo)
```json
{
  "title": "Omelete de queijo",
  "description": "Rápida e sem erro.",
  "servings": 1,
  "prep_minutes": 10,
  "difficulty": "facil",
  "ingredients": [
    { "name": "Ovos", "quantity": 3, "unit": "un" },
    { "name": "Queijo muçarela", "quantity": 50, "unit": "g", "note": "ralado" },
    { "name": "Sal" }
  ],
  "steps": [
    { "instruction": "Bata os ovos com o sal." },
    { "instruction": "Leve à frigideira e acrescente o queijo.", "timer_minutes": 4 }
  ],
  "created_by_ai": false
}
```

| Campo | Regra |
|---|---|
| `title` | 3–120 caracteres |
| `description` | até 2000 caracteres |
| `servings` | 1–50 |
| `prep_minutes` | opcional, 1–1440 |
| `ingredients` | 1–60 itens, na ordem em que devem aparecer |
| `steps` | 1–40 passos; `timer_minutes` opcional, 1–600 |

**201 Created** — o detalhe da receita:
```json
{
  "id": 7, "title": "Omelete de queijo", "image_url": null,
  "author": { "id": 1, "username": "leonardo" },
  "ingredient_count": 3, "pantry_have": 2,
  "avg_rating": null, "rating_count": 0, "is_favorite": false, "my_rating": null,
  "ingredients": [ { "id": 1, "name": "Ovos", "quantity": 3.0, "unit": "un", "note": null, "in_pantry": true } ],
  "steps": [ { "id": 1, "position": 0, "instruction": "Bata os ovos com o sal.", "timer_minutes": null } ],
  "...": "demais campos do corpo, created_at, updated_at"
}
```

`pantry_have`, `in_pantry`, `is_favorite` e `my_rating` são calculados **para quem está
vendo**: a mesma receita mostra números diferentes para cada usuário.

**`GET /recipes`** devolve a mesma estrutura sem `ingredients`, `steps` e `my_rating`.
`scope=mine` filtra pelo autor, `scope=favorites` pelas favoritas de quem pede; `q` busca no
título sem diferenciar maiúsculas (os curingas `%` e `_` valem como texto).

**`GET /recipes/{id}/missing-ingredients`**
```json
[ { "name": "Queijo muçarela", "quantity": 50.0, "unit": "g" } ]
```

**`PUT /recipes/{id}/image`** — `multipart/form-data` com o arquivo no campo `file`. JPEG, PNG
ou WebP, até 5 MB. O formato é identificado pelo conteúdo, não pelo `Content-Type`; a imagem é
reduzida a 1600 px no maior lado e gravada como WebP, sem metadados EXIF. Devolve o detalhe da
receita, com `image_url` relativo à URL da API (`/media/recipes/<arquivo>.webp`).

**`PUT /recipes/{id}/rating`** com `{ "stars": 4 }` devolve os números atualizados:
```json
{ "avg_rating": 4.5, "rating_count": 2, "my_rating": 4 }
```

**`POST /recipes/{id}/comments`** com `{ "content": "Ficou ótima!" }` (1–1000 caracteres)
devolve `201` com `{ id, content, author, created_at }`.

| Erro | Quando |
|---|---|
| `403 Forbidden` | alterar, apagar ou trocar a foto da receita de outra pessoa; avaliar a própria receita; apagar comentário alheio em receita alheia |
| `404 Not Found` | receita inexistente, ou comentário que não pertence à receita da URL |
| `413 Content Too Large` | foto acima de 5 MB |
| `415 Unsupported Media Type` | o arquivo não é uma imagem JPEG, PNG ou WebP válida |
| `422 Unprocessable Entity` | validação falhou |

## Lista de compras

**`POST /shopping-list`**
```json
{ "items": [ { "name": "Café", "quantity": 500, "unit": "g", "category": "bebidas" } ], "source": "manual" }
```

Devolve **200** com a lista inteira atualizada — e não `201`: um item repetido ainda não
comprado soma na linha existente em vez de criar outra. `source` aceita `manual` ou `ia`;
`receita` é exclusivo de `from-recipe`.

**`POST /shopping-list/from-recipe/{id}?servings=4`**
```json
{ "added": 2, "items": [ "...lista atualizada..." ] }
```

**`POST /shopping-list/checkout`** — leva os itens marcados (`checked: true`) para a despensa,
somando aos existentes, e os remove da lista, numa transação só:
```json
{ "moved": 3, "pantry": [ "...despensa atualizada..." ] }
```

## IA

Nenhuma rota de IA grava no banco: todas devolvem uma proposta para a pessoa revisar, e salvar
é feito depois pelas rotas acima, com a validação de sempre. Os erros do provedor seguem o
mesmo mapeamento de `POST /chat` (`429`, `502`, `503`, `504`, `400`). Uma resposta do modelo
fora do formato esperado também é `502`.

**`POST /ai/recipe-draft`** — `{ "request": "um jantar rápido", "use_pantry": true }`
(`request` com 3–2000 caracteres). Devolve uma receita no formato do corpo de `POST /recipes`.

**`POST /ai/pantry-parse`** — `{ "text": "comprei 2 kg de arroz e uma dúzia de ovos" }`
```json
{ "items": [ { "name": "Arroz", "quantity": 2.0, "unit": "kg", "category": "graos", "expires_on": null } ] }
```

**`POST /ai/shopping-suggestions`** — `{ "goal": "café da manhã da semana" }` (`goal` opcional)
```json
{
  "suggestions": [
    { "name": "Pão de forma", "quantity": 1, "unit": "pacote", "category": "padaria",
      "reason": "Para acompanhar os ovos e a muçarela no café da manhã." }
  ]
}
```
