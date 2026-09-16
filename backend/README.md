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
