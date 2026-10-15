"""Regra de negócio de receitas.

Receitas são públicas: qualquer usuário autenticado lê qualquer receita. Só o
autor altera ou apaga. Por isso aqui a resposta para "não é seu" é 403, e não o
404 da despensa — o recurso existe e é visível, só não pertence a quem pediu.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Recipe, RecipeFavorite, RecipeIngredient, RecipeStep
from app.schemas.recipe import RecipeCreate, RecipeScope


class RecipeNotFoundError(Exception):
    """A receita não existe."""


class NotRecipeAuthorError(Exception):
    """A receita existe, mas pertence a outro usuário."""


def _with_relations():
    # selectinload busca autor, ingredientes e passos de todas as receitas em
    # poucas consultas. Sem isso, listar 50 receitas dispararia uma consulta
    # por receita para cada relacionamento — o clássico problema N+1.
    return (
        selectinload(Recipe.author),
        selectinload(Recipe.ingredients),
        selectinload(Recipe.steps),
    )


def list_recipes(
    db: Session,
    user_id: int,
    *,
    scope: RecipeScope = "all",
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Recipe]:
    query = select(Recipe).options(*_with_relations())

    if scope == "mine":
        query = query.where(Recipe.author_id == user_id)
    elif scope == "favorites":
        query = query.join(
            RecipeFavorite,
            (RecipeFavorite.recipe_id == Recipe.id) & (RecipeFavorite.user_id == user_id),
        )

    if search:
        # O termo entra como parâmetro da consulta, nunca concatenado ao SQL.
        # Os curingas do LIKE (% e _) digitados pelo usuário são escapados para
        # valerem como texto, e não como padrão.
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(Recipe.title.ilike(f"%{escaped}%", escape="\\"))

    query = query.order_by(Recipe.created_at.desc(), Recipe.id.desc()).limit(limit).offset(offset)
    return list(db.scalars(query))


def get_recipe(db: Session, recipe_id: int) -> Recipe:
    recipe = db.scalar(select(Recipe).options(*_with_relations()).where(Recipe.id == recipe_id))
    if recipe is None:
        raise RecipeNotFoundError(recipe_id)
    return recipe


def get_own_recipe(db: Session, user_id: int, recipe_id: int) -> Recipe:
    """A receita, se existir e for de quem pediu."""
    recipe = get_recipe(db, recipe_id)
    if recipe.author_id != user_id:
        raise NotRecipeAuthorError(recipe_id)
    return recipe


def create_recipe(db: Session, user_id: int, data: RecipeCreate) -> Recipe:
    recipe = Recipe(author_id=user_id)
    _apply(recipe, data)
    db.add(recipe)
    db.commit()
    return get_recipe(db, recipe.id)


def replace_recipe(db: Session, user_id: int, recipe_id: int, data: RecipeCreate) -> Recipe:
    """PUT: o corpo é a receita inteira, e substitui a anterior.

    Ingredientes e passos não são editados um a um: a lista nova substitui a
    antiga. Para o formulário isso é natural (ele sempre envia tudo), e evita
    uma API de "mover o passo 3 para a posição 1".
    """
    recipe = get_own_recipe(db, user_id, recipe_id)
    _apply(recipe, data)
    db.commit()
    db.expire_all()
    return get_recipe(db, recipe_id)


def delete_recipe(db: Session, user_id: int, recipe_id: int) -> str | None:
    """Apaga a receita e devolve o nome da imagem, para o chamador remover o arquivo.

    O arquivo só deve sair do disco depois do commit: se o commit falhar, a
    receita continua existindo e precisa continuar com a sua foto.
    """
    recipe = get_own_recipe(db, user_id, recipe_id)
    image = recipe.image_filename
    db.delete(recipe)
    db.commit()
    return image


def _apply(recipe: Recipe, data: RecipeCreate) -> None:
    recipe.title = data.title
    recipe.description = data.description
    recipe.servings = data.servings
    recipe.prep_minutes = data.prep_minutes
    recipe.difficulty = data.difficulty
    recipe.created_by_ai = data.created_by_ai
    recipe.ingredients = [
        RecipeIngredient(position=index, **ingredient.model_dump())
        for index, ingredient in enumerate(data.ingredients)
    ]
    recipe.steps = [
        RecipeStep(position=index, **step.model_dump()) for index, step in enumerate(data.steps)
    ]
