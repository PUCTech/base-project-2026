"""Testes das rotas de autenticação."""

from fastapi.testclient import TestClient

from tests.conftest import PASSWORD, USERNAME


class TestRegister:
    def test_cadastro_devolve_201_e_o_usuario(self, client: TestClient):
        response = client.post(
            "/auth/register", json={"username": USERNAME, "password": PASSWORD}
        )
        assert response.status_code == 201

        body = response.json()
        assert body["username"] == USERNAME
        assert isinstance(body["id"], int)

    def test_resposta_nunca_expoe_senha_nem_hash(self, client: TestClient):
        response = client.post(
            "/auth/register", json={"username": USERNAME, "password": PASSWORD}
        )
        corpo_bruto = response.text
        assert "password" not in response.json()
        assert "password_hash" not in response.json()
        # Nem o hash, nem a senha, em nenhum campo da resposta.
        assert PASSWORD not in corpo_bruto
        assert "$2b$" not in corpo_bruto

    def test_username_duplicado_devolve_409(self, client: TestClient, registered_user):
        response = client.post(
            "/auth/register", json={"username": USERNAME, "password": "outra-senha-456"}
        )
        assert response.status_code == 409

    def test_senha_curta_devolve_422(self, client: TestClient):
        response = client.post(
            "/auth/register", json={"username": USERNAME, "password": "curta"}
        )
        assert response.status_code == 422

    def test_username_com_caractere_invalido_devolve_422(self, client: TestClient):
        response = client.post(
            "/auth/register", json={"username": "usuario com espaco", "password": PASSWORD}
        )
        assert response.status_code == 422

    def test_campo_faltando_devolve_422(self, client: TestClient):
        assert client.post("/auth/register", json={"username": USERNAME}).status_code == 422


class TestLogin:
    def test_credenciais_corretas_devolvem_token(self, client: TestClient, registered_user):
        response = client.post(
            "/auth/login", json={"username": USERNAME, "password": PASSWORD}
        )
        assert response.status_code == 200

        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]
        assert body["expires_in"] > 0

    def test_senha_errada_devolve_401(self, client: TestClient, registered_user):
        response = client.post(
            "/auth/login", json={"username": USERNAME, "password": "senha-errada-123"}
        )
        assert response.status_code == 401

    def test_usuario_inexistente_devolve_401(self, client: TestClient):
        response = client.post(
            "/auth/login", json={"username": "nao.existe", "password": PASSWORD}
        )
        assert response.status_code == 401

    def test_mensagem_de_erro_nao_revela_se_a_conta_existe(
        self, client: TestClient, registered_user
    ):
        """Mensagens diferentes permitiriam enumerar contas válidas."""
        senha_errada = client.post(
            "/auth/login", json={"username": USERNAME, "password": "senha-errada-123"}
        )
        inexistente = client.post(
            "/auth/login", json={"username": "nao.existe", "password": PASSWORD}
        )
        assert senha_errada.json() == inexistente.json()

    def test_username_fora_do_padrao_devolve_401_e_nao_422(self, client: TestClient):
        """No login, valor fora do padrão é credencial errada — não erro de
        validação. Um 422 aqui entregaria a regra de formação das senhas."""
        response = client.post(
            "/auth/login", json={"username": "x", "password": "z"}
        )
        assert response.status_code == 401


class TestMe:
    def test_token_valido_devolve_o_proprio_usuario(
        self, client: TestClient, auth_headers, registered_user
    ):
        response = client.get("/auth/me", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["id"] == registered_user["id"]

    def test_sem_header_authorization_devolve_401(self, client: TestClient):
        assert client.get("/auth/me").status_code == 401

    def test_token_invalido_devolve_401(self, client: TestClient):
        response = client.get(
            "/auth/me", headers={"Authorization": "Bearer nao-e-um-token"}
        )
        assert response.status_code == 401

    def test_esquema_errado_devolve_401(self, client: TestClient, auth_headers):
        """Basic em vez de Bearer não deve ser aceito."""
        token = auth_headers["Authorization"].removeprefix("Bearer ")
        response = client.get("/auth/me", headers={"Authorization": f"Basic {token}"})
        assert response.status_code == 401
