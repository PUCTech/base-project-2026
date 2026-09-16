"""Testes do CRUD do próprio usuário."""

from fastapi.testclient import TestClient

from tests.conftest import PASSWORD, USERNAME


class TestUpdate:
    def test_troca_de_username(self, client: TestClient, auth_headers):
        response = client.patch(
            "/users/me", headers=auth_headers, json={"username": "novo.nome"}
        )
        assert response.status_code == 200
        assert response.json()["username"] == "novo.nome"

    def test_troca_de_senha_passa_a_valer_no_login(self, client: TestClient, auth_headers):
        nova = "nova-senha-456789"
        assert (
            client.patch("/users/me", headers=auth_headers, json={"password": nova}).status_code
            == 200
        )

        antiga = client.post("/auth/login", json={"username": USERNAME, "password": PASSWORD})
        assert antiga.status_code == 401

        atual = client.post("/auth/login", json={"username": USERNAME, "password": nova})
        assert atual.status_code == 200

    def test_atualizacao_parcial_nao_apaga_o_outro_campo(
        self, client: TestClient, auth_headers
    ):
        """Mudar só o username não pode invalidar a senha — é o que aconteceria
        se o update tratasse 'campo ausente' como 'campo definido como nulo'."""
        assert (
            client.patch(
                "/users/me", headers=auth_headers, json={"username": "so.o.nome"}
            ).status_code
            == 200
        )

        login = client.post("/auth/login", json={"username": "so.o.nome", "password": PASSWORD})
        assert login.status_code == 200

    def test_username_ja_usado_devolve_409(self, client: TestClient, auth_headers):
        client.post("/auth/register", json={"username": "ja.existe", "password": PASSWORD})

        response = client.patch(
            "/users/me", headers=auth_headers, json={"username": "ja.existe"}
        )
        assert response.status_code == 409

    def test_manter_o_proprio_username_nao_conflita(self, client: TestClient, auth_headers):
        """Reenviar o username atual não pode colidir com o próprio usuário."""
        response = client.patch(
            "/users/me", headers=auth_headers, json={"username": USERNAME}
        )
        assert response.status_code == 200

    def test_corpo_vazio_devolve_422(self, client: TestClient, auth_headers):
        assert client.patch("/users/me", headers=auth_headers, json={}).status_code == 422

    def test_sem_token_devolve_401(self, client: TestClient):
        assert client.patch("/users/me", json={"username": "x.y.z"}).status_code == 401

    def test_resposta_nunca_expoe_o_hash(self, client: TestClient, auth_headers):
        response = client.patch(
            "/users/me", headers=auth_headers, json={"password": "outra-senha-999"}
        )
        assert "$2b$" not in response.text
        assert "password_hash" not in response.json()


class TestDelete:
    def test_remocao_devolve_204_sem_corpo(self, client: TestClient, auth_headers):
        response = client.delete("/users/me", headers=auth_headers)
        assert response.status_code == 204
        assert response.content == b""

    def test_token_antigo_perde_acesso_apos_a_remocao(self, client: TestClient, auth_headers):
        """O JWT continua criptograficamente válido depois do DELETE — sessão
        sem estado não tem como ser revogada. O que barra o acesso é o usuário
        não existir mais no banco."""
        client.delete("/users/me", headers=auth_headers)
        assert client.get("/auth/me", headers=auth_headers).status_code == 401

    def test_username_fica_livre_apos_a_remocao(self, client: TestClient, auth_headers):
        client.delete("/users/me", headers=auth_headers)
        response = client.post(
            "/auth/register", json={"username": USERNAME, "password": PASSWORD}
        )
        assert response.status_code == 201

    def test_sem_token_devolve_401(self, client: TestClient):
        assert client.delete("/users/me").status_code == 401


class TestIsolamentoEntreContas:
    def test_o_token_decide_de_quem_sao_os_dados(self, client: TestClient, auth_headers):
        """Mesmo enviando o id de outra conta no corpo, a rota opera sobre o
        usuário do token. É o que impede alterar a conta alheia trocando um
        número no JSON."""
        outro = client.post(
            "/auth/register", json={"username": "outra.conta", "password": PASSWORD}
        ).json()

        response = client.patch(
            "/users/me",
            headers=auth_headers,
            json={"id": outro["id"], "username": "nome.novo"},
        )
        assert response.status_code == 200
        assert response.json()["id"] != outro["id"]

        # A outra conta continua intacta e com o login funcionando.
        login_outro = client.post(
            "/auth/login", json={"username": "outra.conta", "password": PASSWORD}
        )
        assert login_outro.status_code == 200

    def test_o_token_de_um_usuario_nao_apaga_a_conta_do_outro(
        self, client: TestClient, auth_headers
    ):
        client.post("/auth/register", json={"username": "sobrevivente", "password": PASSWORD})
        client.delete("/users/me", headers=auth_headers)

        login = client.post(
            "/auth/login", json={"username": "sobrevivente", "password": PASSWORD}
        )
        assert login.status_code == 200
