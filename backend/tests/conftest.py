"""Fixtures compartilhadas pelos testes.

Cada teste roda contra um banco SQLite em memória, criado e destruído na hora.
O ganho não é só velocidade: um teste nunca enxerga o que outro escreveu, então
não existe ordem de execução que faça a suíte passar ou falhar.

A troca por SQLite tem um custo honesto: ela não cobre o que é específico do
PostgreSQL. Os testes aqui exercitam regra de negócio e contrato HTTP; o
comportamento no Postgres de verdade é verificado pela coleção Postman rodando
contra o ambiente do docker-compose.
"""

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.routers import ai, auth, chat, pantry, recipe_social, recipes, shopping, users
from app.services import storage

USERNAME = "usuario.teste"
PASSWORD = "senha-de-teste-123"
OTHER_USERNAME = "outra.pessoa"


@pytest.fixture(autouse=True)
def media_dir(tmp_path, monkeypatch):
    """Cada teste grava fotos num diretório temporário próprio, nunca no real."""
    monkeypatch.setattr(storage.settings, "media_dir", str(tmp_path / "media"))
    return tmp_path / "media"


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        # SQLite em memória cria um banco novo por conexão. StaticPool força
        # todas as conexões a compartilharem a mesma, senão o TestClient não
        # enxergaria as tabelas criadas aqui.
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # O SQLite ignora foreign keys a menos que isso seja ligado por conexão.
    #
    # Sem este PRAGMA, o ON DELETE CASCADE de messages.user_id simplesmente não
    # acontece nos testes — e um teste de cascata passaria no PostgreSQL e
    # falharia aqui, ou pior, o contrário: o teste passaria sem cascata alguma
    # e a diferença só apareceria em produção.
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    """Cliente HTTP apontando para o banco da fixture `db`.

    A aplicação é montada aqui a partir dos mesmos routers de produção, em vez
    de importar `app.main.app`: o `lifespan` de lá roda `create_all` contra o
    PostgreSQL configurado no ambiente, e um teste não deve tocar nele.
    """
    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(chat.router)
    app.include_router(pantry.router)
    app.include_router(recipes.router)
    app.include_router(recipe_social.router)
    app.include_router(shopping.router)
    app.include_router(ai.router)

    # Substitui a sessão real pela de teste em todas as rotas de uma vez.
    app.dependency_overrides[get_db] = lambda: db

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def registered_user(client: TestClient) -> dict:
    response = client.post(
        "/auth/register", json={"username": USERNAME, "password": PASSWORD}
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def auth_headers(client: TestClient, registered_user: dict) -> dict[str, str]:
    response = client.post(
        "/auth/login", json={"username": USERNAME, "password": PASSWORD}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def other_auth_headers(client: TestClient) -> dict[str, str]:
    """Uma segunda conta, para provar que um usuário não alcança os dados do outro."""
    client.post("/auth/register", json={"username": OTHER_USERNAME, "password": PASSWORD})
    response = client.post(
        "/auth/login", json={"username": OTHER_USERNAME, "password": PASSWORD}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
