"""Rotas de receitas.

Leitura aberta a qualquer usuário autenticado; escrita só para o autor.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas.recipe import (
    MissingIngredient,
    RecipeCreate,
    RecipeDetail,
    RecipeScope,
    RecipeSummary,
)
from app.services import recipe_views
from app.services.recipes import (
    NotRecipeAuthorError,
    RecipeNotFoundError,
    create_recipe,
    delete_recipe,
    get_recipe,
    list_recipes,
    replace_recipe,
)

router = APIRouter(prefix="/recipes", tags=["recipes"])

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receita não encontrada")
NOT_AUTHOR = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN, detail="Só o autor pode alterar esta receita"
)


@router.get("", response_model=list[RecipeSummary], summary="Lista receitas")
def read_recipes(
    scope: RecipeScope = "all",
    q: str | None = Query(default=None, max_length=100, description="Busca no título"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RecipeSummary]:
    recipes = list_recipes(
        db, current_user.id, scope=scope, search=q, limit=limit, offset=offset
    )
    return recipe_views.summarize(db, current_user.id, recipes)


@router.post(
    "",
    response_model=RecipeDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Cria uma receita",
)
def add_recipe(
    data: RecipeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecipeDetail:
    recipe = create_recipe(db, current_user.id, data)
    return recipe_views.detail(db, current_user.id, recipe)


@router.get("/{recipe_id}", response_model=RecipeDetail, summary="Detalhe de uma receita")
def read_recipe(
    recipe_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecipeDetail:
    try:
        recipe = get_recipe(db, recipe_id)
    except RecipeNotFoundError:
        raise NOT_FOUND from None
    return recipe_views.detail(db, current_user.id, recipe)


@router.put("/{recipe_id}", response_model=RecipeDetail, summary="Substitui uma receita")
def update_recipe(
    recipe_id: int,
    data: RecipeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecipeDetail:
    try:
        recipe = replace_recipe(db, current_user.id, recipe_id, data)
    except RecipeNotFoundError:
        raise NOT_FOUND from None
    except NotRecipeAuthorError:
        raise NOT_AUTHOR from None
    return recipe_views.detail(db, current_user.id, recipe)


@router.delete(
    "/{recipe_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Remove uma receita",
)
def remove_recipe(
    recipe_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    try:
        delete_recipe(db, current_user.id, recipe_id)
    except RecipeNotFoundError:
        raise NOT_FOUND from None
    except NotRecipeAuthorError:
        raise NOT_AUTHOR from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{recipe_id}/missing-ingredients",
    response_model=list[MissingIngredient],
    summary="O que falta na despensa para fazer a receita",
)
def read_missing_ingredients(
    recipe_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MissingIngredient]:
    try:
        recipe = get_recipe(db, recipe_id)
    except RecipeNotFoundError:
        raise NOT_FOUND from None
    return recipe_views.missing_ingredients(db, current_user.id, recipe)
