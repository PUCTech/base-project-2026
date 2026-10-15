"""Testes das rotas de chat.

O provedor de LLM é substituído por um dublê: os testes verificam o contrato da
rota, a persistência e o contexto enviado, não a qualidade da resposta do
modelo. Chamar a API real
aqui tornaria a suíte lenta, dependente de rede, gastadora de cota e — pior —
não determinística.
"""

import pytest
from fastapi.testclient import TestClient

from app.services import kitchen_ai
from app.services.llm import ContentBlockedError, LLMTimeoutError, LLMUnavailableError
from tests.conftest import PASSWORD

RESPOSTA = "Cold start é a latência da primeira requisição após a ociosidade."


@pytest.fixture
def llm_responde(monkeypatch):
    """Faz o provedor devolver uma resposta fixa."""
    monkeypatch.setattr(kitchen_ai, "ask_llm", lambda pergunta, **contexto: RESPOSTA)


@pytest.fixture
def llm_falha(monkeypatch):
    """Devolve uma função que configura a falha desejada."""

    def configurar(excecao: Exception):
        def levantar(pergunta: str, **contexto):
            raise excecao

        monkeypatch.setattr(kitchen_ai, "ask_llm", levantar)

    return configurar


class TestEnvioDeMensagem:
    def test_devolve_a_resposta_do_modelo(self, client: TestClient, auth_headers, llm_responde):
        response = client.post("/chat", headers=auth_headers, json={"message": "O que é cold start?"})

        assert response.status_code == 200
        body = response.json()
        assert body["reply"] == RESPOSTA
        assert "created_at" in body

    def test_grava_pergunta_e_resposta_no_historico(
        self, client: TestClient, auth_headers, llm_responde
    ):
        client.post("/chat", headers=auth_headers, json={"message": "O que é cold start?"})

        historico = client.get("/chat/history", headers=auth_headers).json()["messages"]

        assert [m["role"] for m in historico] == ["user", "assistant"]
        assert historico[0]["content"] == "O que é cold start?"
        assert historico[1]["content"] == RESPOSTA

    def test_a_pergunta_e_enviada_sem_espaco_sobrando(
        self, client: TestClient, auth_headers, monkeypatch
    ):
        recebido = {}
        monkeypatch.setattr(
            kitchen_ai, "ask_llm", lambda p, **contexto: recebido.setdefault("pergunta", p) or RESPOSTA
        )

        client.post("/chat", headers=auth_headers, json={"message": "  Com espaços  "})
        assert recebido["pergunta"] == "Com espaços"

    def test_sem_token_devolve_401(self, client: TestClient, llm_responde):
        assert client.post("/chat", json={"message": "Olá"}).status_code == 401

    @pytest.mark.parametrize(
        "mensagem", ["", "   ", "\n\t "], ids=["vazia", "espacos", "quebras"]
    )
    def test_mensagem_em_branco_devolve_422(
        self, client: TestClient, auth_headers, llm_responde, mensagem
    ):
        response = client.post("/chat", headers=auth_headers, json={"message": mensagem})
        assert response.status_code == 422

    def test_mensagem_muito_longa_devolve_422(self, client: TestClient, auth_headers, llm_responde):
        response = client.post("/chat", headers=auth_headers, json={"message": "a" * 4001})
        assert response.status_code == 422

    def test_mensagem_em_branco_nao_chega_ao_provedor(
        self, client: TestClient, auth_headers, monkeypatch
    ):
        """Validação rejeitada não pode gastar cota do provedor."""
        chamadas = []
        monkeypatch.setattr(
            kitchen_ai, "ask_llm", lambda p, **contexto: chamadas.append(p) or RESPOSTA
        )

        client.post("/chat", headers=auth_headers, json={"message": "   "})
        assert chamadas == []


class TestFalhasDoProvedor:
    def test_timeout_vira_504(self, client: TestClient, auth_headers, llm_falha):
        llm_falha(LLMTimeoutError("demorou"))
        response = client.post("/chat", headers=auth_headers, json={"message": "Olá"})
        assert response.status_code == 504

    def test_indisponivel_vira_502(self, client: TestClient, auth_headers, llm_falha):
        llm_falha(LLMUnavailableError("caiu"))
        response = client.post("/chat", headers=auth_headers, json={"message": "Olá"})
        assert response.status_code == 502

    def test_conteudo_barrado_vira_400(self, client: TestClient, auth_headers, llm_falha):
        llm_falha(ContentBlockedError("SAFETY"))
        response = client.post("/chat", headers=auth_headers, json={"message": "Olá"})
        assert response.status_code == 400

    def test_o_erro_do_provedor_nao_vaza_para_a_resposta(
        self, client: TestClient, auth_headers, llm_falha
    ):
        """Detalhe de infraestrutura do provedor fica no log, não na resposta."""
        llm_falha(LLMUnavailableError("Provedor respondeu 401: API key inválida abc123"))
        response = client.post("/chat", headers=auth_headers, json={"message": "Olá"})

        assert "abc123" not in response.text
        assert "API key" not in response.text

    def test_falha_do_provedor_nao_deixa_pergunta_orfa(
        self, client: TestClient, auth_headers, llm_falha
    ):
        """Gravar a pergunta antes da chamada encheria o histórico de perguntas
        sem resposta toda vez que o provedor falhasse."""
        llm_falha(LLMUnavailableError("caiu"))
        client.post("/chat", headers=auth_headers, json={"message": "Pergunta perdida"})

        historico = client.get("/chat/history", headers=auth_headers).json()["messages"]
        assert historico == []


class TestHistorico:
    def test_vazio_para_usuario_novo(self, client: TestClient, auth_headers):
        assert client.get("/chat/history", headers=auth_headers).json()["messages"] == []

    def test_ordem_cronologica(self, client: TestClient, auth_headers, llm_responde):
        for i in range(3):
            client.post("/chat", headers=auth_headers, json={"message": f"Pergunta {i}"})

        historico = client.get("/chat/history", headers=auth_headers).json()["messages"]

        assert len(historico) == 6
        assert [m["content"] for m in historico if m["role"] == "user"] == [
            "Pergunta 0",
            "Pergunta 1",
            "Pergunta 2",
        ]

    def test_limit_mantem_as_mais_recentes(self, client: TestClient, auth_headers, llm_responde):
        for i in range(5):
            client.post("/chat", headers=auth_headers, json={"message": f"Pergunta {i}"})

        historico = client.get("/chat/history?limit=2", headers=auth_headers).json()["messages"]

        assert len(historico) == 2
        # O corte tira as antigas, não as novas.
        assert historico[-1]["content"] == RESPOSTA

    @pytest.mark.parametrize("limit", [0, -1, 201])
    def test_limit_fora_da_faixa_devolve_422(self, client: TestClient, auth_headers, limit):
        assert client.get(f"/chat/history?limit={limit}", headers=auth_headers).status_code == 422

    def test_sem_token_devolve_401(self, client: TestClient):
        assert client.get("/chat/history").status_code == 401

    def test_um_usuario_nao_ve_o_historico_do_outro(
        self, client: TestClient, auth_headers, llm_responde
    ):
        """O user_id vem do token, nunca da requisição."""
        client.post("/chat", headers=auth_headers, json={"message": "Segredo do primeiro"})

        client.post("/auth/register", json={"username": "intruso", "password": PASSWORD})
        token_intruso = client.post(
            "/auth/login", json={"username": "intruso", "password": PASSWORD}
        ).json()["access_token"]

        historico = client.get(
            "/chat/history", headers={"Authorization": f"Bearer {token_intruso}"}
        ).json()["messages"]

        assert historico == []

    def test_apagar_a_conta_apaga_as_mensagens(
        self, client: TestClient, auth_headers, llm_responde, db
    ):
        from app.models import Message

        client.post("/chat", headers=auth_headers, json={"message": "Some comigo"})
        assert db.query(Message).count() == 2

        client.delete("/users/me", headers=auth_headers)

        db.expire_all()
        assert db.query(Message).count() == 0
