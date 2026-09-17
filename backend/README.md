# Backend — FastAPI

## Rodar localmente

Precisa de um PostgreSQL acessível. A partir da Fase 4, `docker compose up` na raiz
resolve banco e API juntos; até lá, um container avulso serve:

```bash
docker run -d --rm --name chatia-db \
  -e POSTGRES_USER=chatia -e POSTGRES_PASSWORD=chatia-local -e POSTGRES_DB=chatia \
  -p 5433:5432 postgres:16-alpine
```

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt

export DATABASE_URL='postgresql+psycopg2://chatia:chatia-local@localhost:5433/chatia'
export JWT_SECRET_KEY="$(openssl rand -hex 32)"

.venv/bin/uvicorn app.main:app --reload
```

- API: <http://localhost:8000>
- Swagger UI: <http://localhost:8000/docs>

## Lint e testes

```bash
.venv/bin/ruff check .        # lint
.venv/bin/ruff format .       # formatação
.venv/bin/pytest              # testes
```

## Organização

```
app/
├── main.py          # aplicação, CORS, registro dos routers
├── config.py        # variáveis de ambiente validadas com pydantic-settings
├── database.py      # engine, sessão e Base do SQLAlchemy
├── dependencies.py  # get_current_user: resolve o usuário a partir do token
├── routers/         # camada HTTP: rotas e status codes
├── schemas/         # Pydantic: validação da entrada e forma da saída
├── models/          # SQLAlchemy: tabelas e relacionamentos
└── services/        # regra de negócio: hash, sessão, LLM
```

A dependência aponta numa direção só: `routers` → `services` → `models`. Um módulo de
`services/` não importa nada de `routers/` e não conhece `Request` nem `HTTPException` —
ele sinaliza problemas com exceções próprias, e o router decide qual status code cada uma
vira. É isso que permite testar a regra de negócio sem subir a API.

## Detalhes que não são óbvios no código

**As tabelas são criadas com `Base.metadata.create_all` na subida**, não por migração.
Basta para o escopo do projeto, mas tem um limite importante: `create_all` só cria tabela
que ainda não existe — nunca altera uma existente. Se você renomear uma coluna no model, o
banco continua com a antiga e a divergência só aparece na primeira query que quebrar. Em
produção de verdade, Alembic.

**A senha passa por SHA-256 antes do bcrypt** (`app/services/security.py`). O bcrypt
ignora tudo além do 72º byte; sem o pré-hash, uma senha longa teria o final descartado em
silêncio, e duas senhas com os mesmos 72 primeiros bytes seriam a mesma senha.

**O login gasta tempo de propósito quando o usuário não existe.** Sem isso a resposta de
"usuário inexistente" volta mais rápido que a de "senha errada", e essa diferença permite
descobrir quais contas existem — mesmo com as duas respondendo o mesmo `401`.

**`psycopg2-binary` é adequado aqui, mas não para produção séria**: ele traz a libpq
compilada junto, o que é ótimo para desenvolvimento e CI. O pacote `psycopg2` (sem
`-binary`) compila contra a libpq do sistema e é o recomendado pelos mantenedores para
produção.

**Os testes rodam em SQLite, não em PostgreSQL.** Cada teste ganha um banco em memória
criado e destruído na hora, então nenhum teste enxerga o que outro escreveu e não existe
ordem de execução que faça a suíte passar ou falhar. O custo é honesto: SQLite não cobre o
que é específico do Postgres. Os testes exercitam regra de negócio e contrato HTTP; o
comportamento no banco real é verificado pela coleção Postman contra o ambiente do
docker-compose.

**`conftest.py` monta a aplicação em vez de importar `app.main.app`.** O `lifespan` de lá
roda `create_all` contra o PostgreSQL configurado no ambiente — um teste não deve tocar nele.

**`app/main.py` aparece com 0% de cobertura** justamente por isso. Não é código sem teste:
é código que os testes deliberadamente não importam.

**`HTTPBearer` é usado com `auto_error=False`.** Com o padrão `True`, o FastAPI responde
`403` quando o header `Authorization` falta — e `403` é a resposta errada: pela RFC 7235,
`401` é "não sei quem você é" e `403` é "sei quem você é, e você não pode". Quem chega sem
token está no primeiro caso. Foi um teste que pegou essa divergência do contrato.

**O algoritmo do JWT é passado como lista fechada na validação.** Aceitar o algoritmo que o
próprio token declara é a falha clássica do JWT: o atacante troca o header para `alg: none`
e passa a assinar tokens sozinho.

## Docker

A imagem é construída em dois estágios. O primeiro compila as dependências em wheels; o
segundo só as instala. Assim o compilador e os headers de build não chegam à imagem final —
e o que não está na imagem não precisa ser corrigido quando aparece uma CVE.

O `COPY requirements.txt` acontece **antes** do `COPY app`. É isso que faz o cache do Docker
funcionar: enquanto as dependências não mudam, a camada de `pip install` é reaproveitada e
nenhuma reinstalação roda a cada alteração no código.

O container roda como `appuser` (uid 1000), não como root. O padrão do Docker é root, e um
processo exposto à internet rodando como root transforma qualquer execução remota de código
em controle total do container.

```bash
docker exec chatia-backend id
# uid=1000(appuser) gid=1000(appuser) groups=1000(appuser)
```

Nenhum segredo entra na imagem: o `.dockerignore` barra o `.env`, e as variáveis chegam em
tempo de execução pelo compose. Dá para auditar:

```bash
docker image inspect puctech-backend --format '{{range .Config.Env}}{{println .}}{{end}}'
docker history puctech-backend --no-trunc --format '{{.CreatedBy}}' | grep -i secret
```

## Nomes de modelo do Gemini expiram

Este projeto nasceu apontando para `gemini-2.0-flash`. Na primeira chamada real, o provedor
respondeu:

```
404: This model models/gemini-2.0-flash is no longer available.
     Please update your code to use models/gemini-3.6-flash
```

Não é um caso raro — é o ciclo normal do provedor. Três consequências que já estão no código:

1. **O modelo é configurável por ambiente** (`GEMINI_MODEL`). Trocá-lo não exige deploy de
   código novo.
2. **A mensagem de erro indica o substituto.** Quando o `POST /chat` devolver `502`, o motivo
   real está no log do backend (`docker compose logs backend`), não na resposta HTTP — e é lá
   que o provedor diz qual modelo usar.
3. **A lista atual sai da própria API:**
   ```bash
   curl -H "x-goog-api-key: $GEMINI_API_KEY" \
     https://generativelanguage.googleapis.com/v1beta/models
   ```
   Atenção: essa lista inclui modelos que a sua chave **não** pode usar. `gemini-2.5-flash`
   aparece nela e responde `404 "no longer available to new users"`.

Existe o alias `gemini-flash-latest`, que nunca expira. O custo é que a versão muda sob os
seus pés — hoje ele resolve para `gemini-3.8-flash`, que durante os testes desta fase estava
devolvendo `503 "high demand"`. Por isso o padrão aqui é uma versão fixa: previsível, ao
preço de precisar ser atualizada de tempos em tempos.

## Retentativa nas falhas temporárias

O plano gratuito devolve `503 "This model is currently experiencing high demand. Spikes in
demand are usually temporary. Please try again later."` com alguma frequência. A própria
mensagem pede nova tentativa, então insistir é o comportamento pedido — não uma gambiarra.

`ask_llm` tenta até 3 vezes em `429`, `500` e `503`, com espera dobrando a cada rodada
(1 s, 2 s) mais um *jitter* aleatório. O jitter existe para que vários usuários que falharam
juntos não voltem todos no mesmo instante, recriando o pico de demanda que causou o erro.
Se o provedor mandar um `Retry-After`, ele vale mais que a fórmula — limitado a 10 s, para
que um cabeçalho absurdo não prenda a requisição.

O que **não** é retentado:

- **Timeout.** O *read timeout* já é de 60 s; uma segunda espera dessas estouraria o tempo que
  o navegador aguarda, e o usuário veria a aba travada em vez de um erro.
- **`400`, `401`, `403`, `404`.** Chave inválida ou modelo inexistente não melhoram na segunda
  tentativa — insistir só atrasaria a resposta de erro.
