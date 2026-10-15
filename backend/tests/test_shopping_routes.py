"""Testes da lista de compras e do ciclo receita → lista → despensa."""

import pytest
from fastapi.testclient import TestClient

from tests.helpers import adicionar_na_despensa, criar_receita


def adicionar(client: TestClient, headers: dict, *itens: dict, source: str = "manual") -> list[dict]:
    response = client.post(
        "/shopping-list", headers=headers, json={"items": list(itens), "source": source}
    )
    assert response.status_code == 200, response.text
    return response.json()


def por_nome(lista: list[dict]) -> dict[str, dict]:
    return {item["name"]: item for item in lista}


class TestItens:
    def test_adiciona_e_lista(self, client: TestClient, auth_headers):
        lista = adicionar(client, auth_headers, {"name": "Café", "quantity": 500, "unit": "g"})

        assert len(lista) == 1
        assert lista[0]["checked"] is False
        assert lista[0]["source"] == "manual"

    def test_item_repetido_soma_na_mesma_linha(self, client: TestClient, auth_headers):
        adicionar(client, auth_headers, {"name": "Ovos", "quantity": 6, "unit": "un"})
        lista = adicionar(client, auth_headers, {"name": "ovo", "quantity": 6, "unit": "un"})

        assert len(lista) == 1
        assert lista[0]["quantity"] == 12

    def test_unidades_incomparaveis_viram_duas_linhas(self, client: TestClient, auth_headers):
        lista = adicionar(
            client,
            auth_headers,
            {"name": "Tomate", "quantity": 3, "unit": "un"},
            {"name": "Tomate", "quantity": 500, "unit": "g"},
        )
        assert len(lista) == 2

    def test_item_ja_marcado_nao_recebe_soma(self, client: TestClient, auth_headers):
        """O que já está no carrinho é outra compra."""
        item = adicionar(client, auth_headers, {"name": "Leite", "quantity": 1, "unit": "l"})[0]
        client.patch(f"/shopping-list/{item['id']}", headers=auth_headers, json={"checked": True})

        lista = adicionar(client, auth_headers, {"name": "Leite", "quantity": 1, "unit": "l"})
        assert len(lista) == 2

    def test_cliente_nao_declara_origem_receita(self, client: TestClient, auth_headers):
        """'receita' é exclusivo da rota que calcula o que falta."""
        response = client.post(
            "/shopping-list", headers=auth_headers, json={"items": [{"name": "Sal"}], "source": "receita"}
        )
        assert response.status_code == 422

    def test_nao_comprados_primeiro(self, client: TestClient, auth_headers):
        lista = adicionar(client, auth_headers, {"name": "Arroz"}, {"name": "Feijão"})
        arroz = por_nome(lista)["Arroz"]
        client.patch(f"/shopping-list/{arroz['id']}", headers=auth_headers, json={"checked": True})

        nomes = [i["name"] for i in client.get("/shopping-list", headers=auth_headers).json()]
        assert nomes == ["Feijão", "Arroz"]

    def test_remove_e_descarta_marcados(self, client: TestClient, auth_headers):
        lista = adicionar(client, auth_headers, {"name": "Arroz"}, {"name": "Feijão"}, {"name": "Sal"})
        itens = por_nome(lista)
        client.delete(f"/shopping-list/{itens['Arroz']['id']}", headers=auth_headers)
        client.patch(f"/shopping-list/{itens['Sal']['id']}", headers=auth_headers, json={"checked": True})

        assert client.delete("/shopping-list/checked", headers=auth_headers).status_code == 204
        restantes = [i["name"] for i in client.get("/shopping-list", headers=auth_headers).json()]
        assert restantes == ["Feijão"]

    def test_lista_e_privada(self, client: TestClient, auth_headers, other_auth_headers):
        item = adicionar(client, auth_headers, {"name": "Café"})[0]

        assert client.get("/shopping-list", headers=other_auth_headers).json() == []
        response = client.patch(
            f"/shopping-list/{item['id']}", headers=other_auth_headers, json={"checked": True}
        )
        assert response.status_code == 404

    @pytest.mark.parametrize("corpo", [{}, {"checked": None}, {"name": "  "}])
    def test_patch_invalido_devolve_422(self, client: TestClient, auth_headers, corpo):
        item = adicionar(client, auth_headers, {"name": "Café"})[0]
        response = client.patch(f"/shopping-list/{item['id']}", headers=auth_headers, json=corpo)
        assert response.status_code == 422


class TestOQueFaltaNaReceita:
    def test_adiciona_so_o_que_falta(self, client: TestClient, auth_headers):
        adicionar_na_despensa(client, auth_headers, name="Ovos", quantity=1, unit="un")
        adicionar_na_despensa(client, auth_headers, name="Sal")
        receita = criar_receita(client, auth_headers)

        response = client.post(f"/shopping-list/from-recipe/{receita['id']}", headers=auth_headers)

        assert response.status_code == 200
        body = response.json()
        assert body["added"] == 2
        itens = por_nome(body["items"])
        assert itens["Ovos"]["quantity"] == 2
        assert itens["Queijo muçarela"]["quantity"] == 50
        assert itens["Ovos"]["source"] == "receita"
        assert itens["Ovos"]["recipe_id"] == receita["id"]

    def test_ajusta_as_quantidades_pelas_porcoes(self, client: TestClient, auth_headers):
        receita = criar_receita(client, auth_headers)  # rende 1 porção, 3 ovos
        body = client.post(
            f"/shopping-list/from-recipe/{receita['id']}?servings=2", headers=auth_headers
        ).json()
        assert por_nome(body["items"])["Ovos"]["quantity"] == 6

    def test_despensa_completa_nao_adiciona_nada(self, client: TestClient, auth_headers):
        adicionar_na_despensa(client, auth_headers, name="Ovos", quantity=12, unit="un")
        adicionar_na_despensa(client, auth_headers, name="Muçarela", quantity=1, unit="kg")
        adicionar_na_despensa(client, auth_headers, name="Sal")
        receita = criar_receita(
            client, auth_headers, ingredients=[{"name": "Ovos", "quantity": 2, "unit": "un"}, {"name": "Sal"}]
        )

        body = client.post(f"/shopping-list/from-recipe/{receita['id']}", headers=auth_headers).json()
        assert (body["added"], body["items"]) == (0, [])

    def test_duas_receitas_somam_o_mesmo_ingrediente(self, client: TestClient, auth_headers):
        primeira = criar_receita(client, auth_headers)
        segunda = criar_receita(client, auth_headers, title="Outra omelete")
        client.post(f"/shopping-list/from-recipe/{primeira['id']}", headers=auth_headers)
        body = client.post(f"/shopping-list/from-recipe/{segunda['id']}", headers=auth_headers).json()

        assert por_nome(body["items"])["Ovos"]["quantity"] == 6

    def test_apagar_a_receita_mantem_o_item_na_lista(self, client: TestClient, auth_headers):
        receita = criar_receita(client, auth_headers)
        client.post(f"/shopping-list/from-recipe/{receita['id']}", headers=auth_headers)
        client.delete(f"/recipes/{receita['id']}", headers=auth_headers)

        lista = client.get("/shopping-list", headers=auth_headers).json()
        assert len(lista) == 3
        assert all(item["recipe_id"] is None for item in lista)

    def test_receita_inexistente_devolve_404(self, client: TestClient, auth_headers):
        assert client.post("/shopping-list/from-recipe/999", headers=auth_headers).status_code == 404


class TestFinalizarCompra:
    def test_leva_os_marcados_para_a_despensa(self, client: TestClient, auth_headers):
        adicionar_na_despensa(client, auth_headers, name="Arroz", quantity=1, unit="kg", category="graos")
        lista = adicionar(
            client,
            auth_headers,
            {"name": "Arroz", "quantity": 500, "unit": "g", "category": "graos"},
            {"name": "Café", "quantity": 250, "unit": "g", "category": "bebidas"},
            {"name": "Detergente"},
        )
        for item in lista:
            if item["name"] != "Detergente":
                client.patch(f"/shopping-list/{item['id']}", headers=auth_headers, json={"checked": True})

        response = client.post("/shopping-list/checkout", headers=auth_headers)

        assert response.status_code == 200
        body = response.json()
        assert body["moved"] == 2
        despensa = por_nome(body["pantry"])
        assert despensa["Arroz"]["quantity"] == 1.5
        assert despensa["Café"]["category"] == "bebidas"
        restantes = client.get("/shopping-list", headers=auth_headers).json()
        assert [i["name"] for i in restantes] == ["Detergente"]

    def test_sem_marcados_nao_muda_nada(self, client: TestClient, auth_headers):
        adicionar(client, auth_headers, {"name": "Café"})
        body = client.post("/shopping-list/checkout", headers=auth_headers).json()

        assert (body["moved"], body["pantry"]) == (0, [])
        assert len(client.get("/shopping-list", headers=auth_headers).json()) == 1

    def test_ciclo_completo(self, client: TestClient, auth_headers):
        """Receita → o que falta → lista → compra → despensa → receita completa."""
        receita = criar_receita(client, auth_headers)
        assert receita["pantry_have"] == 0

        lista = client.post(
            f"/shopping-list/from-recipe/{receita['id']}", headers=auth_headers
        ).json()["items"]
        for item in lista:
            client.patch(f"/shopping-list/{item['id']}", headers=auth_headers, json={"checked": True})
        client.post("/shopping-list/checkout", headers=auth_headers)

        depois = client.get(f"/recipes/{receita['id']}", headers=auth_headers).json()
        assert depois["pantry_have"] == depois["ingredient_count"]
