"""Testes do CRUD de receitas."""

import pytest
from fastapi.testclient import TestClient

from tests.helpers import RECEITA, adicionar_na_despensa, criar_receita


class TestCriacao:
    def test_cria_com_ingredientes_e_passos_na_ordem(self, client: TestClient, auth_headers):
        receita = criar_receita(client, auth_headers)

        assert receita["title"] == "Omelete de queijo"
        assert [i["name"] for i in receita["ingredients"]] == ["Ovos", "Queijo muçarela", "Sal"]
        assert [s["position"] for s in receita["steps"]] == [0, 1]
        assert receita["steps"][1]["timer_minutes"] == 4
        assert receita["author"]["username"] == "usuario.teste"
        assert receita["created_by_ai"] is False

    @pytest.mark.parametrize(
        "campos",
        [
            {"title": "ab"},
            {"ingredients": []},
            {"steps": []},
            {"servings": 0},
            {"difficulty": "impossivel"},
            {"steps": [{"instruction": "Asse", "timer_minutes": 0}]},
            {"ingredients": [{"name": "Farinha", "quantity": -1}]},
        ],
        ids=[
            "titulo-curto",
            "sem-ingredientes",
            "sem-passos",
            "zero-porcoes",
            "dificuldade-invalida",
            "timer-zero",
            "quantidade-negativa",
        ],
    )
    def test_receita_invalida_devolve_422(self, client: TestClient, auth_headers, campos):
        response = client.post("/recipes", headers=auth_headers, json={**RECEITA, **campos})
        assert response.status_code == 422

    def test_sem_token_devolve_401(self, client: TestClient):
        assert client.post("/recipes", json=RECEITA).status_code == 401
        assert client.get("/recipes").status_code == 401


class TestLeitura:
    def test_qualquer_usuario_le_qualquer_receita(
        self, client: TestClient, auth_headers, other_auth_headers
    ):
        receita = criar_receita(client, auth_headers)
        response = client.get(f"/recipes/{receita['id']}", headers=other_auth_headers)
        assert response.status_code == 200

    def test_inexistente_devolve_404(self, client: TestClient, auth_headers):
        assert client.get("/recipes/999", headers=auth_headers).status_code == 404

    def test_lista_da_mais_nova_para_a_mais_antiga(self, client: TestClient, auth_headers):
        for titulo in ["Primeira", "Segunda", "Terceira"]:
            criar_receita(client, auth_headers, title=titulo)

        titulos = [r["title"] for r in client.get("/recipes", headers=auth_headers).json()]
        assert titulos == ["Terceira", "Segunda", "Primeira"]

    def test_escopo_mine_filtra_pelo_autor(
        self, client: TestClient, auth_headers, other_auth_headers
    ):
        criar_receita(client, auth_headers, title="Minha")
        criar_receita(client, other_auth_headers, title="Da outra pessoa")

        todas = client.get("/recipes", headers=auth_headers).json()
        minhas = client.get("/recipes?scope=mine", headers=auth_headers).json()

        assert len(todas) == 2
        assert [r["title"] for r in minhas] == ["Minha"]

    def test_busca_no_titulo_sem_diferenciar_caixa(self, client: TestClient, auth_headers):
        criar_receita(client, auth_headers, title="Bolo de cenoura")
        criar_receita(client, auth_headers, title="Arroz de forno")

        achadas = client.get("/recipes?q=BOLO", headers=auth_headers).json()
        assert [r["title"] for r in achadas] == ["Bolo de cenoura"]

    def test_curinga_do_like_vale_como_texto(self, client: TestClient, auth_headers):
        """Sem escapar, buscar '%' traria todas as receitas."""
        criar_receita(client, auth_headers, title="Bolo de cenoura")
        assert client.get("/recipes?q=%25", headers=auth_headers).json() == []

    def test_paginacao(self, client: TestClient, auth_headers):
        for i in range(5):
            criar_receita(client, auth_headers, title=f"Receita {i}")

        pagina = client.get("/recipes?limit=2&offset=2", headers=auth_headers).json()
        assert [r["title"] for r in pagina] == ["Receita 2", "Receita 1"]


class TestCruzamentoComADespensa:
    def test_marca_o_que_a_despensa_de_quem_ve_cobre(self, client: TestClient, auth_headers):
        adicionar_na_despensa(client, auth_headers, name="Ovos", quantity=12, unit="un")
        adicionar_na_despensa(client, auth_headers, name="Sal")
        receita = criar_receita(client, auth_headers)

        marcados = {i["name"]: i["in_pantry"] for i in receita["ingredients"]}
        assert marcados == {"Ovos": True, "Queijo muçarela": False, "Sal": True}
        assert (receita["pantry_have"], receita["ingredient_count"]) == (2, 3)

    def test_a_mesma_receita_vista_por_outra_despensa(
        self, client: TestClient, auth_headers, other_auth_headers
    ):
        adicionar_na_despensa(client, auth_headers, name="Ovos", quantity=12, unit="un")
        receita = criar_receita(client, auth_headers)

        vista_pela_outra = client.get(f"/recipes/{receita['id']}", headers=other_auth_headers).json()
        assert vista_pela_outra["pantry_have"] == 0

    def test_o_que_falta(self, client: TestClient, auth_headers):
        adicionar_na_despensa(client, auth_headers, name="Ovos", quantity=1, unit="un")
        adicionar_na_despensa(client, auth_headers, name="Sal")
        receita = criar_receita(client, auth_headers)

        falta = client.get(
            f"/recipes/{receita['id']}/missing-ingredients", headers=auth_headers
        ).json()

        assert falta == [
            {"name": "Ovos", "quantity": 2, "unit": "un"},
            {"name": "Queijo muçarela", "quantity": 50, "unit": "g"},
        ]


class TestEdicao:
    def test_put_substitui_ingredientes_e_passos(self, client: TestClient, auth_headers):
        receita = criar_receita(client, auth_headers)
        nova = {
            **RECEITA,
            "title": "Omelete simples",
            "ingredients": [{"name": "Ovos", "quantity": 2, "unit": "un"}],
            "steps": [{"instruction": "Frite."}],
        }

        response = client.put(f"/recipes/{receita['id']}", headers=auth_headers, json=nova)

        assert response.status_code == 200
        body = response.json()
        assert body["title"] == "Omelete simples"
        assert [i["name"] for i in body["ingredients"]] == ["Ovos"]
        assert len(body["steps"]) == 1

    def test_so_o_autor_edita(self, client: TestClient, auth_headers, other_auth_headers):
        """403, e não 404: a receita é pública, então a existência dela não é
        segredo — o que falta é permissão."""
        receita = criar_receita(client, auth_headers)
        response = client.put(
            f"/recipes/{receita['id']}", headers=other_auth_headers, json={**RECEITA, "title": "Hackeada"}
        )

        assert response.status_code == 403
        assert client.get(f"/recipes/{receita['id']}", headers=auth_headers).json()["title"] == RECEITA["title"]

    def test_so_o_autor_remove(self, client: TestClient, auth_headers, other_auth_headers):
        receita = criar_receita(client, auth_headers)
        assert client.delete(f"/recipes/{receita['id']}", headers=other_auth_headers).status_code == 403
        assert client.delete(f"/recipes/{receita['id']}", headers=auth_headers).status_code == 204
        assert client.get(f"/recipes/{receita['id']}", headers=auth_headers).status_code == 404

    def test_apagar_a_conta_apaga_as_receitas(self, client: TestClient, auth_headers, other_auth_headers):
        criar_receita(client, auth_headers)
        client.delete("/users/me", headers=auth_headers)
        assert client.get("/recipes", headers=other_auth_headers).json() == []
