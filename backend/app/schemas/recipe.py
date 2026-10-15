"""Schemas de receitas."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.common import Difficulty, ItemName, OptionalText, PositiveQuantity, Unit

RecipeScope = Literal["all", "mine", "favorites"]


class IngredientIn(BaseModel):
    name: ItemName
    quantity: PositiveQuantity = None
    unit: Unit = None
    note: OptionalText = None


class StepIn(BaseModel):
    instruction: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]
    timer_minutes: int | None = Field(default=None, ge=1, le=600)


class RecipeIn(BaseModel):
    """Conteúdo de uma receita: o que o autor escreve.

    É também o formato do rascunho gerado pela IA. Usar o mesmo schema nos dois
    caminhos garante que um rascunho da IA passe pela mesma validação que uma
    receita digitada à mão — nada que o modelo invente entra por uma porta
    mais larga.
    """

    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=120)]
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] = ""
    servings: int = Field(default=2, ge=1, le=50)
    prep_minutes: int | None = Field(default=None, ge=1, le=1440)
    difficulty: Difficulty = "facil"
    ingredients: list[IngredientIn] = Field(min_length=1, max_length=60)
    steps: list[StepIn] = Field(min_length=1, max_length=40)


class RecipeCreate(RecipeIn):
    """Corpo de POST /recipes e de PUT /recipes/{id}."""

    # Marca exibida na tela ("criada com IA"). Vem do cliente porque é o
    # cliente que sabe se o formulário partiu de um rascunho da IA; é
    # informativa, não dá permissão a nada.
    created_by_ai: bool = False


class AuthorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str


class IngredientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    quantity: float | None
    unit: str | None
    note: str | None
    # Calculado para quem está vendo: a mesma receita mostra ✓ diferentes para
    # cada usuário, conforme a despensa de cada um.
    in_pantry: bool = False


class StepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    position: int
    instruction: str
    timer_minutes: int | None


class RecipeSummary(BaseModel):
    """Uma receita na listagem: sem ingredientes e passos, com os números."""

    id: int
    title: str
    description: str
    servings: int
    prep_minutes: int | None
    difficulty: Difficulty
    created_by_ai: bool
    author: AuthorRead
    ingredient_count: int
    # Quantos ingredientes da receita a despensa de quem está vendo cobre.
    pantry_have: int
    avg_rating: float | None
    rating_count: int
    is_favorite: bool
    created_at: datetime
    updated_at: datetime


class RecipeDetail(RecipeSummary):
    ingredients: list[IngredientRead]
    steps: list[StepRead]
    # A nota que quem está vendo deu, para a tela marcar as estrelas.
    my_rating: int | None


class MissingIngredient(BaseModel):
    """Um item que falta para fazer a receita."""

    name: str
    quantity: float | None
    unit: str | None


class RatingIn(BaseModel):
    """Corpo de PUT /recipes/{id}/rating."""

    stars: int = Field(ge=1, le=5)


class RatingSummary(BaseModel):
    """Resposta de PUT e DELETE /recipes/{id}/rating: os números já atualizados."""

    avg_rating: float | None
    rating_count: int
    my_rating: int | None


class CommentIn(BaseModel):
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class CommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    author: AuthorRead
    created_at: datetime
