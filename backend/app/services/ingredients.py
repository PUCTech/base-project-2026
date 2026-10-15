"""Comparação entre o que uma receita pede e o que existe na despensa.

Funções puras: não acessam banco nem HTTP. Recebem qualquer objeto com os
atributos certos — um model do SQLAlchemy em produção, um dataclass no teste —
e por isso são testadas sem subir nada.

É uma heurística, e os limites dela são conhecidos:

- "Tomates" casa com "tomate" e "Açúcar" com "acucar" (plural e acento);
- "leite" casa com "leite integral" — o item da despensa pode ser mais
  específico que o da receita;
- mas "leite" também casa com "leite condensado", que é outro produto. Resolver
  isso exigiria entender o que cada palavra significa.

Esse último caso é exatamente onde a IA ajuda: a sugestão de compras
(`services/kitchen_ai.py`) entrega ao modelo a despensa e as receitas, e ele
lida com sinônimos e variações que regra fixa nenhuma cobre. A regra fixa fica
com o que precisa ser previsível e instantâneo — marcar ✓ na tela da receita.
"""

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

# Palavras que não distinguem um ingrediente de outro: "farinha de trigo" e
# "farinha trigo" são o mesmo item.
STOPWORDS = frozenset({"a", "o", "e", "de", "da", "do", "das", "dos", "com", "em"})

# Unidades escritas de formas diferentes que significam a mesma coisa.
UNIT_ALIASES = {
    "g": "g",
    "gr": "g",
    "grama": "g",
    "gramas": "g",
    "kg": "kg",
    "quilo": "kg",
    "quilos": "kg",
    "kilo": "kg",
    "kilos": "kg",
    "ml": "ml",
    "mililitro": "ml",
    "mililitros": "ml",
    "l": "l",
    "lt": "l",
    "litro": "l",
    "litros": "l",
    "un": "un",
    "und": "un",
    "unid": "un",
    "unidade": "un",
    "unidades": "un",
}

# Fator para a unidade-base de cada grandeza. Só converte dentro da mesma
# grandeza: "2 xícaras" e "300 g" não têm conversão honesta sem saber a
# densidade do ingrediente.
UNIT_FACTORS = {
    "g": ("massa", 1.0),
    "kg": ("massa", 1000.0),
    "ml": ("volume", 1.0),
    "l": ("volume", 1000.0),
}


def ingredient_key(name: str) -> str:
    """Forma canônica de um nome, usada para comparar e para buscar.

    "Tomates Italianos" → "tomate italiano"; "Açúcar" → "acucar".
    """
    without_accents = "".join(
        char
        for char in unicodedata.normalize("NFKD", name)
        if not unicodedata.combining(char)
    ).lower()

    words = "".join(char if char.isalnum() else " " for char in without_accents).split()
    return " ".join(_singular(word) for word in words if word not in STOPWORDS)


def _singular(word: str) -> str:
    """Singular aproximado do português.

    Não precisa acertar a gramática: como os dois lados da comparação passam
    pela mesma função, "lápis" → "lapi" não atrapalha — os dois viram "lapi".
    Só precisa levar plural e singular para a mesma forma.
    """
    if len(word) <= 3:
        return word
    if word.endswith(("oes", "aes", "aos")):  # limões, pães, grãos
        return word[:-3] + "ao"
    if word.endswith(("res", "zes")):  # açúcares, nozes
        return word[:-2]
    if word.endswith("ns"):  # atuns
        return word[:-2] + "m"
    if word.endswith("s"):
        return word[:-1]
    return word


def normalize_unit(unit: str | None) -> str | None:
    """"Gramas" → "g", "Litro" → "l". Unidade desconhecida passa como veio."""
    if unit is None:
        return None
    cleaned = ingredient_key(unit).replace(" ", "")
    if not cleaned:
        return None
    return UNIT_ALIASES.get(cleaned, cleaned)


def convert(quantity: float, from_unit: str | None, to_unit: str | None) -> float | None:
    """Converte a quantidade, ou devolve None se as unidades não são comparáveis."""
    source, target = normalize_unit(from_unit), normalize_unit(to_unit)
    if source == target:
        return quantity
    if source not in UNIT_FACTORS or target not in UNIT_FACTORS:
        return None

    source_kind, source_factor = UNIT_FACTORS[source]
    target_kind, target_factor = UNIT_FACTORS[target]
    if source_kind != target_kind:
        return None
    return quantity * source_factor / target_factor


def names_match(needed_key: str, available_key: str) -> bool:
    """O item disponível atende ao pedido?

    Todas as palavras do pedido precisam aparecer no item disponível — nessa
    direção, e não na outra: "leite" é atendido por "leite integral", mas
    "leite condensado" não é atendido por "leite".
    """
    needed = set(needed_key.split())
    return bool(needed) and needed <= set(available_key.split())


class NeededItem(Protocol):
    name: str
    quantity: float | None
    unit: str | None


class AvailableItem(Protocol):
    name: str
    quantity: float | None
    unit: str | None


@dataclass(frozen=True)
class Shortfall:
    """O que falta de um ingrediente. `quantity=None`: falta, sem quantidade definida."""

    name: str
    quantity: float | None
    unit: str | None


def shortfall_for(item: NeededItem, pantry: Iterable[AvailableItem]) -> Shortfall | None:
    """Quanto falta de um ingrediente, ou None se a despensa dá conta."""
    key = ingredient_key(item.name)
    # Quantidade zero é "acabou": o item continua cadastrado para lembrar de
    # comprar, mas não conta como disponível.
    candidates = [
        available
        for available in pantry
        if names_match(key, ingredient_key(available.name)) and available.quantity != 0
    ]

    if not candidates:
        return Shortfall(item.name, item.quantity, item.unit)

    # A receita não diz quanto ("sal a gosto"), ou a despensa não controla
    # quanto tem: ter o item já basta.
    if item.quantity is None or any(c.quantity is None for c in candidates):
        return None

    convertible = [
        amount
        for c in candidates
        if (amount := convert(c.quantity, c.unit, item.unit)) is not None
    ]

    # "3 un" de tomate contra "500 g" pedidos: sem como comparar, assumimos que
    # tem. Errar para "tem" custa uma ida ao mercado; errar para "falta"
    # encheria a lista de compras de itens que já estão na despensa.
    if not convertible:
        return None

    missing = item.quantity - sum(convertible)
    if missing <= 0:
        return None
    return Shortfall(item.name, round(missing, 2), item.unit)


def shortfalls(
    needed: Iterable[NeededItem], pantry: Iterable[AvailableItem]
) -> list[Shortfall]:
    """Tudo o que falta para uma lista de ingredientes."""
    pantry = list(pantry)
    return [s for item in needed if (s := shortfall_for(item, pantry)) is not None]
