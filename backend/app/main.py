"""Ponto de entrada da API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, engine
from app.routers import auth, chat, pantry, recipe_social, recipes, users

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Cria as tabelas que ainda não existem, na subida da aplicação.
    #
    # Serve bem para o escopo deste projeto, mas não substitui migrações:
    # `create_all` só cria tabela nova, nunca altera uma existente. Renomear uma
    # coluna aqui não faz nada, e a divergência entre model e banco só aparece
    # na primeira query que quebrar. Em produção de verdade, Alembic.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Chat com IA — API",
    description="Backend do projeto de referência: autenticação e chat com LLM.",
    version="0.6.0",
    lifespan=lifespan,
)

# CORS restrito às origens declaradas no ambiente. `allow_origins=["*"]` seria
# mais cômodo e abriria a API para qualquer site chamar em nome do usuário.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(chat.router)
app.include_router(pantry.router)
app.include_router(recipes.router)
app.include_router(recipe_social.router)


@app.get("/health", tags=["health"], summary="Liveness check")
def health() -> dict[str, str]:
    """Usado pelo healthcheck do Docker e pelo monitoramento do Render."""
    return {"status": "ok"}
