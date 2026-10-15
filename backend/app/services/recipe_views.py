"""Monta a visão de uma receita para quem está olhando.

A tabela guarda a receita; a resposta da API acrescenta o que depende de quem
pergunta — quais ingredientes a despensa dessa pessoa cobre, se ela favoritou,
que nota deu. Esse cálculo mora aqui para que o router continue só traduzindo
HTTP e o serviço de receitas continue só cuidando de gravar.
"""

from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.models import PantryItem, Recipe
from app.schemas.recipe import (
    AuthorRead,
    IngredientRead,
    MissingIngredient,
    RecipeDetail,
    RecipeSummary,
    StepRead,
)
from app.services.ingredients import shortfall_for, shortfalls
from app.services.pantry import list_pantry


def summarize(db: Session, viewer_id: int, recipes: Sequence[Recipe]) -> list[RecipeSummary]:
    # A despensa é lida uma vez para a listagem inteira, não uma vez por receita.
    pantry = list_pantry(db, viewer_id)
    return [_summary(recipe, pantry) for recipe in recipes]


def detail(db: Session, viewer_id: int, recipe: Recipe) -> RecipeDetail:
    pantry = list_pantry(db, viewer_id)
    ingredients = [
        IngredientRead.model_validate(ingredient).model_copy(
            update={"in_pantry": shortfall_for(ingredient, pantry) is None}
        )
        for ingredient in recipe.ingredients
    ]
    return RecipeDetail(
        **_summary(recipe, pantry).model_dump(),
        ingredients=ingredients,
        steps=[StepRead.model_validate(step) for step in recipe.steps],
    )


def missing_ingredients(db: Session, viewer_id: int, recipe: Recipe) -> list[MissingIngredient]:
    return [
        MissingIngredient(name=s.name, quantity=s.quantity, unit=s.unit)
        for s in shortfalls(recipe.ingredients, list_pantry(db, viewer_id))
    ]


def _summary(recipe: Recipe, pantry: list[PantryItem]) -> RecipeSummary:
    missing = len(shortfalls(recipe.ingredients, pantry))
    return RecipeSummary(
        id=recipe.id,
        title=recipe.title,
        description=recipe.description,
        servings=recipe.servings,
        prep_minutes=recipe.prep_minutes,
        difficulty=recipe.difficulty,
        created_by_ai=recipe.created_by_ai,
        author=AuthorRead.model_validate(recipe.author),
        ingredient_count=len(recipe.ingredients),
        pantry_have=len(recipe.ingredients) - missing,
        created_at=recipe.created_at,
        updated_at=recipe.updated_at,
    )
