"""Monta a visão de uma receita para quem está olhando.

A tabela guarda a receita; a resposta da API acrescenta o que depende de quem
pergunta — quais ingredientes a despensa dessa pessoa cobre, se ela favoritou,
que nota deu. Esse cálculo mora aqui para que o router continue só traduzindo
HTTP e o serviço de receitas continue só cuidando de gravar.
"""

from collections.abc import Sequence
from dataclasses import dataclass

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
from app.services.recipe_social import RatingStats, favorite_ids, my_rating, rating_stats


@dataclass
class _Context:
    """O que a visão precisa saber sobre quem está olhando."""

    pantry: list[PantryItem]
    favorites: set[int]
    stats: dict[int, RatingStats]


def _context(db: Session, viewer_id: int, recipes: Sequence[Recipe]) -> _Context:
    # Uma consulta para a despensa, uma para os favoritos e uma para as notas —
    # para a listagem inteira, e não uma de cada por receita.
    ids = [recipe.id for recipe in recipes]
    return _Context(
        pantry=list_pantry(db, viewer_id),
        favorites=favorite_ids(db, viewer_id, ids),
        stats=rating_stats(db, ids),
    )


def summarize(db: Session, viewer_id: int, recipes: Sequence[Recipe]) -> list[RecipeSummary]:
    context = _context(db, viewer_id, recipes)
    return [_summary(recipe, context) for recipe in recipes]


def detail(db: Session, viewer_id: int, recipe: Recipe) -> RecipeDetail:
    context = _context(db, viewer_id, [recipe])
    pantry = context.pantry
    ingredients = [
        IngredientRead.model_validate(ingredient).model_copy(
            update={"in_pantry": shortfall_for(ingredient, pantry) is None}
        )
        for ingredient in recipe.ingredients
    ]
    return RecipeDetail(
        **_summary(recipe, context).model_dump(),
        ingredients=ingredients,
        steps=[StepRead.model_validate(step) for step in recipe.steps],
        my_rating=my_rating(db, viewer_id, recipe.id),
    )


def missing_ingredients(db: Session, viewer_id: int, recipe: Recipe) -> list[MissingIngredient]:
    return [
        MissingIngredient(name=s.name, quantity=s.quantity, unit=s.unit)
        for s in shortfalls(recipe.ingredients, list_pantry(db, viewer_id))
    ]


def _summary(recipe: Recipe, context: _Context) -> RecipeSummary:
    missing = len(shortfalls(recipe.ingredients, context.pantry))
    stats = context.stats.get(recipe.id, RatingStats(average=None, count=0))
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
        avg_rating=stats.average,
        rating_count=stats.count,
        is_favorite=recipe.id in context.favorites,
        created_at=recipe.created_at,
        updated_at=recipe.updated_at,
    )
