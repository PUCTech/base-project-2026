"""Testes da comparação receita × despensa.

Funções puras: nenhum banco, nenhum HTTP. É a parte do sistema com mais regra
e menos infraestrutura, e por isso a mais barata de cobrir bem.
"""

from dataclasses import dataclass

import pytest

from app.services.ingredients import (
    convert,
    ingredient_key,
    names_match,
    normalize_unit,
    shortfall_for,
    shortfalls,
)


@dataclass
class Item:
    name: str
    quantity: float | None = None
    unit: str | None = None


class TestChaveDoIngrediente:
    @pytest.mark.parametrize(
        ("nome", "chave"),
        [
            ("Tomate", "tomate"),
            ("Tomates", "tomate"),
            ("  AÇÚCAR  ", "acucar"),
            ("Açúcares", "acucar"),
            ("Limões", "limao"),
            ("Pães", "pao"),
            ("Farinha de trigo", "farinha trigo"),
            ("Pimenta-do-reino", "pimenta reino"),
            ("Ovos caipiras", "ovo caipira"),
            ("Arroz", "arroz"),
            ("Nozes", "noz"),
        ],
    )
    def test_normaliza_acento_caixa_plural_e_preposicao(self, nome, chave):
        assert ingredient_key(nome) == chave

    def test_plural_e_singular_chegam_na_mesma_chave(self):
        assert ingredient_key("cebola") == ingredient_key("Cebolas")


class TestCorrespondencia:
    def test_item_mais_especifico_atende_pedido_generico(self):
        assert names_match(ingredient_key("leite"), ingredient_key("Leite integral"))

    def test_item_generico_nao_atende_pedido_especifico(self):
        assert not names_match(ingredient_key("leite condensado"), ingredient_key("leite"))

    def test_limite_conhecido_da_heuristica(self):
        """Documentado de propósito: a regra não sabe que leite condensado é
        outro produto. É o tipo de caso que a sugestão por IA resolve."""
        assert names_match(ingredient_key("leite"), ingredient_key("leite condensado"))

    def test_chave_vazia_nao_casa_com_nada(self):
        assert not names_match("", "qualquer coisa")


class TestUnidades:
    @pytest.mark.parametrize(
        ("unidade", "esperado"),
        [("Gramas", "g"), ("kg", "kg"), ("Litro", "l"), ("unidades", "un"), ("xícara", "xicara")],
    )
    def test_normaliza_unidade(self, unidade, esperado):
        assert normalize_unit(unidade) == esperado

    @pytest.mark.parametrize("unidade", [None, "", "   "])
    def test_unidade_vazia_vira_none(self, unidade):
        assert normalize_unit(unidade) is None

    def test_converte_dentro_da_mesma_grandeza(self):
        assert convert(1.5, "kg", "g") == 1500
        assert convert(250, "ml", "litros") == 0.25

    def test_nao_converte_entre_grandezas(self):
        assert convert(1, "kg", "l") is None

    def test_nao_converte_medida_caseira(self):
        """Xícara para grama depende da densidade do ingrediente."""
        assert convert(2, "xícara", "g") is None


class TestOQueFalta:
    def test_ingrediente_ausente_falta_inteiro(self):
        falta = shortfall_for(Item("Ovos", 3, "un"), [Item("Arroz", 1, "kg")])
        assert falta is not None
        assert (falta.quantity, falta.unit) == (3, "un")

    def test_quantidade_suficiente_nao_falta(self):
        assert shortfall_for(Item("Arroz", 500, "g"), [Item("Arroz", 1, "kg")]) is None

    def test_falta_so_a_diferenca(self):
        falta = shortfall_for(Item("Farinha de trigo", 500, "g"), [Item("farinha trigo", 200, "g")])
        assert falta is not None
        assert falta.quantity == 300

    def test_soma_itens_iguais_em_unidades_diferentes(self):
        despensa = [Item("Leite", 500, "ml"), Item("Leite integral", 1, "l")]
        assert shortfall_for(Item("leite", 1.2, "l"), despensa) is None

    def test_quantidade_zero_e_item_que_acabou(self):
        falta = shortfall_for(Item("Sal"), [Item("Sal", 0, "g")])
        assert falta is not None

    def test_receita_sem_quantidade_basta_ter_o_item(self):
        assert shortfall_for(Item("Sal"), [Item("Sal grosso", 1, "kg")]) is None

    def test_despensa_sem_quantidade_conta_como_tem(self):
        assert shortfall_for(Item("Azeite", 50, "ml"), [Item("Azeite")]) is None

    def test_unidades_incomparaveis_assumem_que_tem(self):
        """Errar para 'tem' custa uma ida ao mercado; errar para 'falta' enche a
        lista de compras de itens que já estão em casa."""
        assert shortfall_for(Item("Tomate", 500, "g"), [Item("Tomates", 3, "un")]) is None

    def test_lista_completa(self):
        receita = [Item("Arroz", 200, "g"), Item("Ovos", 2, "un"), Item("Cebola", 1, "un")]
        despensa = [Item("arroz", 1, "kg"), Item("Cebolas", 3, "un")]

        assert [f.name for f in shortfalls(receita, despensa)] == ["Ovos"]
