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
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.routers import auth, users

USERNAME = "usuario.teste"
PASSWORD = "senha-de-teste-123"


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
