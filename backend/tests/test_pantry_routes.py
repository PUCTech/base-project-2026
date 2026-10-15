"""Testes das rotas da despensa."""

import pytest
from fastapi.testclient import TestClient

ARROZ = {"name": "Arroz", "quantity": 2, "unit": "kg", "category": "graos"}


def adicionar(client: TestClient, headers: dict, **campos) -> dict:
    response = client.post("/pantry", headers=headers, json={**ARROZ, **campos})
    assert response.status_code == 201, response.text
    return response.json()


class TestCadastro:
    def test_cria_e_lista(self, client: TestClient, auth_headers):
        criado = adicionar(client, auth_headers, expires_on="2026-12-01")

        assert criado["name"] == "Arroz"
        assert criado["expires_on"] == "2026-12-01"
        assert client.get("/pantry", headers=auth_headers).json() == [criado]

    def test_campos_opcionais_em_branco_viram_null(self, client: TestClient, auth_headers):
        """Formulário HTML manda "" para campo não preenchido."""
        criado = adicionar(client, auth_headers, name="Sal", quantity=None, unit="  ")
        assert criado["unit"] is None
        assert criado["quantity"] is None

    def test_categoria_padrao_e_outros(self, client: TestClient, auth_headers):
        response = client.post("/pantry", headers=auth_headers, json={"name": "Fermento"})
        assert response.json()["category"] == "outros"

    @pytest.mark.parametrize(
        "campos",
        [
            {"name": "   "},
            {"name": "x" * 101},
            {"quantity": -1},
            {"category": "eletronicos"},
            {"expires_on": "amanhã"},
        ],
        ids=["nome-branco", "nome-longo", "quantidade-negativa", "categoria-invalida", "data-invalida"],
    )
    def test_entrada_invalida_devolve_422(self, client: TestClient, auth_headers, campos):
        response = client.post("/pantry", headers=auth_headers, json={**ARROZ, **campos})
        assert response.status_code == 422

    def test_quantidade_zero_e_aceita(self, client: TestClient, auth_headers):
        """Zero é 'acabou': o item fica para lembrar de comprar."""
        assert adicionar(client, auth_headers, quantity=0)["quantity"] == 0

    @pytest.mark.parametrize("nome", ["Arroz", "arroz", "ARROZ ", "Arrozes"])
    def test_item_repetido_devolve_409(self, client: TestClient, auth_headers, nome):
        adicionar(client, auth_headers)
        response = client.post("/pantry", headers=auth_headers, json={**ARROZ, "name": nome})
        assert response.status_code == 409

    def test_sem_token_devolve_401(self, client: TestClient):
        assert client.get("/pantry").status_code == 401
        assert client.post("/pantry", json=ARROZ).status_code == 401


class TestEdicao:
    def test_atualiza_so_o_que_foi_enviado(self, client: TestClient, auth_headers):
        item = adicionar(client, auth_headers)
        response = client.patch(f"/pantry/{item['id']}", headers=auth_headers, json={"quantity": 5})

        assert response.status_code == 200
        assert response.json()["quantity"] == 5
        assert response.json()["unit"] == "kg"

    def test_null_explicito_apaga_o_valor(self, client: TestClient, auth_headers):
        item = adicionar(client, auth_headers, expires_on="2026-12-01")
        response = client.patch(
            f"/pantry/{item['id']}", headers=auth_headers, json={"expires_on": None}
        )
        assert response.json()["expires_on"] is None

    def test_corpo_vazio_devolve_422(self, client: TestClient, auth_headers):
        item = adicionar(client, auth_headers)
        assert client.patch(f"/pantry/{item['id']}", headers=auth_headers, json={}).status_code == 422

    def test_nome_nao_pode_ser_apagado(self, client: TestClient, auth_headers):
        item = adicionar(client, auth_headers)
        response = client.patch(f"/pantry/{item['id']}", headers=auth_headers, json={"name": None})
        assert response.status_code == 422

    def test_renomear_para_nome_existente_devolve_409(self, client: TestClient, auth_headers):
        adicionar(client, auth_headers)
        feijao = adicionar(client, auth_headers, name="Feijão")
        response = client.patch(
            f"/pantry/{feijao['id']}", headers=auth_headers, json={"name": "arroz"}
        )
        assert response.status_code == 409

    def test_remove(self, client: TestClient, auth_headers):
        item = adicionar(client, auth_headers)
        assert client.delete(f"/pantry/{item['id']}", headers=auth_headers).status_code == 204
        assert client.get("/pantry", headers=auth_headers).json() == []

    def test_item_inexistente_devolve_404(self, client: TestClient, auth_headers):
        assert client.delete("/pantry/999", headers=auth_headers).status_code == 404


class TestIsolamentoEntreUsuarios:
    """Despensa é privada. O item de outra pessoa responde 404, e não 403:
    403 confirmaria que aquele id existe."""

    def test_nao_ve_a_despensa_do_outro(self, client: TestClient, auth_headers, other_auth_headers):
        adicionar(client, auth_headers)
        assert client.get("/pantry", headers=other_auth_headers).json() == []

    def test_nao_edita_nem_remove_item_do_outro(
        self, client: TestClient, auth_headers, other_auth_headers
    ):
        item = adicionar(client, auth_headers)

        editar = client.patch(f"/pantry/{item['id']}", headers=other_auth_headers, json={"quantity": 0})
        remover = client.delete(f"/pantry/{item['id']}", headers=other_auth_headers)

        assert (editar.status_code, remover.status_code) == (404, 404)
        assert client.get("/pantry", headers=auth_headers).json()[0]["quantity"] == 2

    def test_o_mesmo_nome_pode_existir_em_despensas_diferentes(
        self, client: TestClient, auth_headers, other_auth_headers
    ):
        adicionar(client, auth_headers)
        adicionar(client, other_auth_headers)


class TestLote:
    def lote(self, client, headers, itens):
        response = client.post("/pantry/batch", headers=headers, json={"items": itens})
        assert response.status_code == 200, response.text
        return {item["name"]: item for item in client.get("/pantry", headers=headers).json()}

    def test_soma_ao_item_existente_convertendo_unidade(self, client: TestClient, auth_headers):
        adicionar(client, auth_headers)  # 2 kg
        despensa = self.lote(client, auth_headers, [{"name": "arroz", "quantity": 500, "unit": "g"}])

        assert despensa["Arroz"]["quantity"] == 2.5
        assert despensa["Arroz"]["unit"] == "kg"

    def test_itens_repetidos_no_mesmo_lote_viram_um_so(self, client: TestClient, auth_headers):
        despensa = self.lote(
            client,
            auth_headers,
            [{"name": "Ovos", "quantity": 6, "unit": "un"}, {"name": "ovo", "quantity": 6, "unit": "un"}],
        )
        assert len(despensa) == 1
        assert despensa["Ovos"]["quantity"] == 12

    def test_item_que_tinha_acabado_assume_a_nova_quantidade(self, client: TestClient, auth_headers):
        adicionar(client, auth_headers, name="Leite", quantity=0, unit=None)
        despensa = self.lote(client, auth_headers, [{"name": "Leite", "quantity": 2, "unit": "l"}])
        assert (despensa["Leite"]["quantity"], despensa["Leite"]["unit"]) == (2, "l")

    def test_unidades_incomparaveis_deixam_de_controlar_quantidade(
        self, client: TestClient, auth_headers
    ):
        """3 un + 500 g não tem total honesto; inventar um número seria pior."""
        adicionar(client, auth_headers, name="Tomate", quantity=3, unit="un")
        despensa = self.lote(client, auth_headers, [{"name": "Tomate", "quantity": 500, "unit": "g"}])
        assert despensa["Tomate"]["quantity"] is None

    def test_mantem_a_validade_mais_proxima(self, client: TestClient, auth_headers):
        adicionar(client, auth_headers, expires_on="2026-11-01")
        despensa = self.lote(
            client, auth_headers, [{"name": "Arroz", "quantity": 1, "unit": "kg", "expires_on": "2027-03-01"}]
        )
        assert despensa["Arroz"]["expires_on"] == "2026-11-01"

    def test_lote_vazio_devolve_422(self, client: TestClient, auth_headers):
        assert client.post("/pantry/batch", headers=auth_headers, json={"items": []}).status_code == 422

    def test_um_item_invalido_barra_o_lote_inteiro(self, client: TestClient, auth_headers):
        response = client.post(
            "/pantry/batch",
            headers=auth_headers,
            json={"items": [{"name": "Arroz"}, {"name": ""}]},
        )
        assert response.status_code == 422
        assert client.get("/pantry", headers=auth_headers).json() == []
