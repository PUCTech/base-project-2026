"""Rotas da lista de compras. Privada, como a despensa."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.routers.recipes import NOT_FOUND as RECIPE_NOT_FOUND
from app.schemas.shopping import (
    CheckoutResult,
    FromRecipeResult,
    ShoppingAdd,
    ShoppingItemRead,
    ShoppingItemUpdate,
)
from app.services import shopping
from app.services.recipes import RecipeNotFoundError, get_recipe
from app.services.shopping import ShoppingItemNotFoundError

router = APIRouter(prefix="/shopping-list", tags=["shopping-list"])

_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Item não encontrado na lista"
)


@router.get("", response_model=list[ShoppingItemRead], summary="Lista de compras")
def read_list(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ShoppingItemRead]:
    return shopping.list_items(db, current_user.id)


@router.post(
    "",
    response_model=list[ShoppingItemRead],
    summary="Adiciona itens, juntando com os repetidos; devolve a lista atualizada",
)
def add_items(
    data: ShoppingAdd,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ShoppingItemRead]:
    """200, e não 201: um item repetido soma a uma linha existente em vez de
    criar outra, então nem toda chamada cria um recurso novo."""
    shopping.add_items(db, current_user.id, data.items, source=data.source)
    return shopping.list_items(db, current_user.id)


@router.post(
    "/from-recipe/{recipe_id}",
    response_model=FromRecipeResult,
    summary="Adiciona o que falta na despensa para fazer a receita",
)
def add_missing_from_recipe(
    recipe_id: int,
    servings: int | None = Query(default=None, ge=1, le=50, description="Ajusta as quantidades"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FromRecipeResult:
    try:
        recipe = get_recipe(db, recipe_id)
    except RecipeNotFoundError:
        raise RECIPE_NOT_FOUND from None
    added = shopping.add_missing_from_recipe(db, current_user.id, recipe, servings)
    return FromRecipeResult(added=added, items=shopping.list_items(db, current_user.id))


@router.post(
    "/checkout",
    response_model=CheckoutResult,
    summary="Finaliza a compra: leva os itens marcados para a despensa",
)
def checkout(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> CheckoutResult:
    moved, pantry = shopping.checkout(db, current_user.id)
    return CheckoutResult(moved=moved, pantry=pantry)


@router.delete(
    "/checked",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Descarta os itens marcados, sem levar para a despensa",
)
def clear_checked(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    shopping.clear_checked(db, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{item_id}", response_model=ShoppingItemRead, summary="Atualiza ou marca um item")
def edit_item(
    item_id: int,
    data: ShoppingItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShoppingItemRead:
    try:
        return shopping.update_item(db, current_user.id, item_id, data)
    except ShoppingItemNotFoundError:
        raise _NOT_FOUND from None


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Remove um item",
)
def remove_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    try:
        shopping.delete_item(db, current_user.id, item_id)
    except ShoppingItemNotFoundError:
        raise _NOT_FOUND from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
