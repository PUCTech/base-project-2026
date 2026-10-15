"""Testes de favoritos, avaliações e comentários."""

import pytest
from fastapi.testclient import TestClient

from tests.helpers import criar_receita


@pytest.fixture
def receita(client: TestClient, auth_headers) -> dict:
    """Uma receita do usuário principal, para a outra conta interagir."""
    return criar_receita(client, auth_headers)


class TestFavoritos:
    def test_favoritar_aparece_no_detalhe_e_no_filtro(
        self, client: TestClient, other_auth_headers, receita
    ):
        url = f"/recipes/{receita['id']}"
        assert client.put(f"{url}/favorite", headers=other_auth_headers).status_code == 204

        assert client.get(url, headers=other_auth_headers).json()["is_favorite"] is True
        favoritas = client.get("/recipes?scope=favorites", headers=other_auth_headers).json()
        assert [r["id"] for r in favoritas] == [receita["id"]]

    def test_favorito_e_por_usuario(self, client: TestClient, auth_headers, other_auth_headers, receita):
        client.put(f"/recipes/{receita['id']}/favorite", headers=other_auth_headers)
        assert client.get("/recipes?scope=favorites", headers=auth_headers).json() == []

    def test_put_e_delete_sao_idempotentes(self, client: TestClient, other_auth_headers, receita):
        """Clique duplo ou retentativa de rede não podem inverter o pedido."""
        url = f"/recipes/{receita['id']}/favorite"
        for _ in range(2):
            assert client.put(url, headers=other_auth_headers).status_code == 204
        assert client.get(f"/recipes/{receita['id']}", headers=other_auth_headers).json()["is_favorite"]

        for _ in range(2):
            assert client.delete(url, headers=other_auth_headers).status_code == 204
        assert not client.get(f"/recipes/{receita['id']}", headers=other_auth_headers).json()["is_favorite"]

    def test_receita_inexistente_devolve_404(self, client: TestClient, auth_headers):
        assert client.put("/recipes/999/favorite", headers=auth_headers).status_code == 404


class TestAvaliacoes:
    def avaliar(self, client, headers, receita_id, estrelas):
        return client.put(f"/recipes/{receita_id}/rating", headers=headers, json={"stars": estrelas})

    def test_avaliar_devolve_os_numeros_atualizados(
        self, client: TestClient, other_auth_headers, receita
    ):
        response = self.avaliar(client, other_auth_headers, receita["id"], 4)

        assert response.status_code == 200
        assert response.json() == {"avg_rating": 4.0, "rating_count": 1, "my_rating": 4}

    def test_avaliar_de_novo_substitui_a_nota(self, client: TestClient, other_auth_headers, receita):
        """Uma nota por pessoa: a segunda chamada atualiza, não soma."""
        self.avaliar(client, other_auth_headers, receita["id"], 2)
        response = self.avaliar(client, other_auth_headers, receita["id"], 5)
        assert response.json() == {"avg_rating": 5.0, "rating_count": 1, "my_rating": 5}

    def test_media_de_varias_pessoas(self, client: TestClient, other_auth_headers, receita):
        self.avaliar(client, other_auth_headers, receita["id"], 5)
        client.post("/auth/register", json={"username": "terceira", "password": "senha-de-teste-123"})
        token = client.post(
            "/auth/login", json={"username": "terceira", "password": "senha-de-teste-123"}
        ).json()["access_token"]
        self.avaliar(client, {"Authorization": f"Bearer {token}"}, receita["id"], 2)

        resumo = client.get("/recipes", headers=other_auth_headers).json()[0]
        assert (resumo["avg_rating"], resumo["rating_count"]) == (3.5, 2)

    def test_nao_avalia_a_propria_receita(self, client: TestClient, auth_headers, receita):
        assert self.avaliar(client, auth_headers, receita["id"], 5).status_code == 403

    @pytest.mark.parametrize("estrelas", [0, 6, -1])
    def test_nota_fora_da_faixa_devolve_422(self, client: TestClient, other_auth_headers, receita, estrelas):
        assert self.avaliar(client, other_auth_headers, receita["id"], estrelas).status_code == 422

    def test_remover_a_nota(self, client: TestClient, other_auth_headers, receita):
        self.avaliar(client, other_auth_headers, receita["id"], 3)
        response = client.delete(f"/recipes/{receita['id']}/rating", headers=other_auth_headers)
        assert response.json() == {"avg_rating": None, "rating_count": 0, "my_rating": None}

    def test_my_rating_no_detalhe(self, client: TestClient, other_auth_headers, receita):
        self.avaliar(client, other_auth_headers, receita["id"], 4)
        detalhe = client.get(f"/recipes/{receita['id']}", headers=other_auth_headers).json()
        assert detalhe["my_rating"] == 4


class TestComentarios:
    def comentar(self, client, headers, receita_id, texto="Ficou ótima!"):
        response = client.post(
            f"/recipes/{receita_id}/comments", headers=headers, json={"content": texto}
        )
        assert response.status_code == 201, response.text
        return response.json()

    def test_comenta_e_lista_em_ordem_cronologica(
        self, client: TestClient, auth_headers, other_auth_headers, receita
    ):
        self.comentar(client, other_auth_headers, receita["id"], "Primeiro")
        self.comentar(client, auth_headers, receita["id"], "Obrigado!")

        comentarios = client.get(f"/recipes/{receita['id']}/comments", headers=auth_headers).json()
        assert [c["content"] for c in comentarios] == ["Primeiro", "Obrigado!"]
        assert comentarios[0]["author"]["username"] == "outra.pessoa"

    @pytest.mark.parametrize("texto", ["", "   ", "x" * 1001])
    def test_comentario_invalido_devolve_422(self, client: TestClient, auth_headers, receita, texto):
        response = client.post(
            f"/recipes/{receita['id']}/comments", headers=auth_headers, json={"content": texto}
        )
        assert response.status_code == 422

    def test_quem_escreveu_apaga(self, client: TestClient, other_auth_headers, receita):
        comentario = self.comentar(client, other_auth_headers, receita["id"])
        url = f"/recipes/{receita['id']}/comments/{comentario['id']}"
        assert client.delete(url, headers=other_auth_headers).status_code == 204

    def test_autor_da_receita_modera(self, client: TestClient, auth_headers, other_auth_headers, receita):
        comentario = self.comentar(client, other_auth_headers, receita["id"])
        url = f"/recipes/{receita['id']}/comments/{comentario['id']}"
        assert client.delete(url, headers=auth_headers).status_code == 204

    def test_terceiros_nao_apagam(self, client: TestClient, auth_headers, other_auth_headers):
        receita_da_outra = criar_receita(client, other_auth_headers)
        comentario = self.comentar(client, other_auth_headers, receita_da_outra["id"])
        url = f"/recipes/{receita_da_outra['id']}/comments/{comentario['id']}"
        assert client.delete(url, headers=auth_headers).status_code == 403

    def test_nao_contorna_a_moderacao_trocando_a_receita_da_url(
        self, client: TestClient, auth_headers, other_auth_headers, receita
    ):
        """O comentário é da receita da outra pessoa. Pôr a receita própria na
        URL não pode dar poder de moderação sobre ele."""
        receita_da_outra = criar_receita(client, other_auth_headers)
        comentario = self.comentar(client, other_auth_headers, receita_da_outra["id"])

        response = client.delete(
            f"/recipes/{receita['id']}/comments/{comentario['id']}", headers=auth_headers
        )
        assert response.status_code == 404

    def test_comentarios_somem_com_a_receita(self, client: TestClient, auth_headers, other_auth_headers, receita):
        self.comentar(client, other_auth_headers, receita["id"])
        client.delete(f"/recipes/{receita['id']}", headers=auth_headers)
        assert client.get(f"/recipes/{receita['id']}/comments", headers=auth_headers).status_code == 404
