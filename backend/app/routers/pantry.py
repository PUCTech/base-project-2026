"""Rotas da despensa.

A despensa é privada: toda rota opera só sobre os itens do usuário do token.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas.pantry import (
    PantryBatchCreate,
    PantryItemCreate,
    PantryItemRead,
    PantryItemUpdate,
)
from app.services.pantry import (
    DuplicatePantryItemError,
    PantryItemNotFoundError,
    add_or_merge,
    create_pantry_item,
    delete_pantry_item,
    list_pantry,
    update_pantry_item,
)

router = APIRouter(prefix="/pantry", tags=["pantry"])

_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Item não encontrado na despensa"
)
_DUPLICATE = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail="Esse item já está na despensa. Edite a quantidade dele.",
)


@router.get("", response_model=list[PantryItemRead], summary="Lista a despensa")
def read_pantry(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[PantryItemRead]:
    return list_pantry(db, current_user.id)


@router.post(
    "",
    response_model=PantryItemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Adiciona um item à despensa",
)
def add_item(
    data: PantryItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PantryItemRead:
    try:
        return create_pantry_item(db, current_user.id, data)
    except DuplicatePantryItemError:
        raise _DUPLICATE from None


@router.post(
    "/batch",
    response_model=list[PantryItemRead],
    summary="Adiciona vários itens, somando aos que já existem",
)
def add_items_in_batch(
    data: PantryBatchCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PantryItemRead]:
    """Diferente do POST unitário, aqui item repetido soma em vez de dar 409.

    É o caminho do cadastro rápido por texto: a IA interpreta "comprei 2 kg de
    arroz e uma dúzia de ovos", o usuário revisa, e a lista inteira entra de
    uma vez.
    """
    return add_or_merge(db, current_user.id, data.items)


@router.patch("/{item_id}", response_model=PantryItemRead, summary="Atualiza um item")
def edit_item(
    item_id: int,
    data: PantryItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PantryItemRead:
    try:
        return update_pantry_item(db, current_user.id, item_id, data)
    except PantryItemNotFoundError:
        raise _NOT_FOUND from None
    except DuplicatePantryItemError:
        raise _DUPLICATE from None


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
        delete_pantry_item(db, current_user.id, item_id)
    except PantryItemNotFoundError:
        raise _NOT_FOUND from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
