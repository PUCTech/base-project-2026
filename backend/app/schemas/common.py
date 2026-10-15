"""Tipos de campo reaproveitados por despensa, receitas e lista de compras.

Declarar a regra uma vez garante que "nome de ingrediente" signifique a mesma
coisa nas três telas — o mesmo limite de tamanho, o mesmo tratamento de espaço
em branco.
"""

from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, StringConstraints

# Categorias fixas, não texto livre: com texto livre, "Laticínios",
# "laticinios" e "Frios e laticínios" viram três grupos diferentes na tela.
Category = Literal[
    "hortifruti",
    "carnes",
    "laticinios",
    "graos",
    "padaria",
    "temperos",
    "doces",
    "bebidas",
    "congelados",
    "outros",
]

Difficulty = Literal["facil", "media", "dificil"]


def _blank_to_none(value: object) -> object:
    """Campo opcional enviado como "" ou "   " é o mesmo que não enviado.

    Formulários HTML mandam string vazia para campo não preenchido; sem isso,
    a unidade "" seria gravada e tratada como uma unidade de verdade.
    """
    if isinstance(value, str) and not value.strip():
        return None
    return value


# strip_whitespace roda antes de min_length: "   " vira "" e é rejeitado.
ItemName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]

# As restrições de texto ficam no `str`, dentro do opcional: aplicadas ao
# `str | None` inteiro, elas tentariam medir o comprimento de None.
Unit = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)] | None,
    BeforeValidator(_blank_to_none),
]

OptionalText = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None,
    BeforeValidator(_blank_to_none),
]

# Quantidade a comprar ou a usar: se informada, é positiva.
PositiveQuantity = Annotated[float | None, Field(gt=0, le=100_000)]
