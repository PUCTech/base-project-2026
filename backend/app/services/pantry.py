"""Regra de negócio da despensa.

Toda consulta filtra por `user_id`, e o `user_id` vem sempre do token. Um item
de outra pessoa é tratado como inexistente: o router responde 404, e não 403,
porque 403 confirmaria que aquele id existe.
"""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import PantryItem
from app.schemas.pantry import PantryItemCreate, PantryItemUpdate
from app.services.ingredients import convert, ingredient_key


class PantryItemNotFoundError(Exception):
    """O item não existe — ou existe, mas é de outro usuário."""


class DuplicatePantryItemError(Exception):
    """Já existe um item com esse nome na despensa."""


def list_pantry(db: Session, user_id: int) -> list[PantryItem]:
    return list(
        db.scalars(
            select(PantryItem)
            .where(PantryItem.user_id == user_id)
            .order_by(PantryItem.category, PantryItem.name_key)
        )
    )


def get_pantry_item(db: Session, user_id: int, item_id: int) -> PantryItem:
    # Filtrar por id E por user_id na mesma consulta. Buscar só pelo id e
    # comparar o dono depois funciona igual — até alguém esquecer a
    # comparação numa rota nova.
    item = db.scalar(
        select(PantryItem).where(PantryItem.id == item_id, PantryItem.user_id == user_id)
    )
    if item is None:
        raise PantryItemNotFoundError(item_id)
    return item


def _find_by_key(db: Session, user_id: int, name_key: str) -> PantryItem | None:
    return db.scalar(
        select(PantryItem).where(PantryItem.user_id == user_id, PantryItem.name_key == name_key)
    )


def create_pantry_item(db: Session, user_id: int, data: PantryItemCreate) -> PantryItem:
    name_key = ingredient_key(data.name)
    if _find_by_key(db, user_id, name_key) is not None:
        raise DuplicatePantryItemError(data.name)

    item = PantryItem(user_id=user_id, name_key=name_key, **data.model_dump())
    db.add(item)
    _commit_or_duplicate(db, data.name)
    db.refresh(item)
    return item


def update_pantry_item(
    db: Session, user_id: int, item_id: int, data: PantryItemUpdate
) -> PantryItem:
    item = get_pantry_item(db, user_id, item_id)
    changes = data.model_dump(exclude_unset=True)

    if "name" in changes:
        new_key = ingredient_key(changes["name"])
        existing = _find_by_key(db, user_id, new_key)
        if existing is not None and existing.id != item.id:
            raise DuplicatePantryItemError(changes["name"])
        item.name_key = new_key

    for field, value in changes.items():
        setattr(item, field, value)

    _commit_or_duplicate(db, item.name)
    db.refresh(item)
    return item


def delete_pantry_item(db: Session, user_id: int, item_id: int) -> None:
    db.delete(get_pantry_item(db, user_id, item_id))
    db.commit()


def add_or_merge(
    db: Session, user_id: int, entries: Iterable[PantryItemCreate]
) -> list[PantryItem]:
    """Adiciona itens à despensa, somando aos que já existem.

    É o que roda no cadastro em lote: comprar arroz com arroz já na despensa
    aumenta a quantidade, em vez de recusar com 409 como faz o cadastro
    unitário.

    Tudo num commit só. Se um item falhar, nenhum entra.
    """
    touched = merge_into_pantry(db, user_id, entries)
    _commit_or_duplicate(db, "lote")
    for item in touched:
        db.refresh(item)
    return touched


def merge_into_pantry(
    db: Session, user_id: int, entries: Iterable[PantryItemCreate]
) -> list[PantryItem]:
    """O mesmo que `add_or_merge`, mas sem commit.

    Existe para quem precisa juntar esta escrita a outras na mesma transação:
    finalizar a compra move os itens para a despensa e os tira da lista, e as
    duas coisas precisam acontecer juntas — uma compra finalizada pela metade
    deixaria a despensa e a lista descasadas.
    """
    touched: list[PantryItem] = []

    for entry in entries:
        name_key = ingredient_key(entry.name)
        item = _find_by_key(db, user_id, name_key)

        if item is None:
            item = PantryItem(user_id=user_id, name_key=name_key, **entry.model_dump())
            db.add(item)
        else:
            _merge_into(item, entry)

        # A sessão usa autoflush=False: sem o flush, um segundo "arroz" no
        # mesmo lote não enxergaria o primeiro e criaria uma linha duplicada.
        db.flush()
        if item not in touched:
            touched.append(item)

    return touched


def _merge_into(item: PantryItem, entry: PantryItemCreate) -> None:
    """Soma a entrada a um item existente com o mesmo nome."""
    if entry.expires_on is not None:
        # Fica a validade mais próxima: é a que precisa de atenção primeiro.
        item.expires_on = min(filter(None, [item.expires_on, entry.expires_on]))

    if entry.quantity is None or item.quantity is None:
        # Um dos lados não controla quantidade; somar não faz sentido.
        return

    if item.quantity == 0:
        # Tinha acabado: a compra define a quantidade e a unidade de novo.
        item.quantity, item.unit = entry.quantity, entry.unit
        return

    added = convert(entry.quantity, entry.unit, item.unit)
    if added is None:
        # "3 un" somado a "500 g": não há total honesto. Em vez de inventar um
        # número, o item passa a "tenho, sem quantidade controlada".
        item.quantity = None
    else:
        item.quantity = round(item.quantity + added, 3)


def _commit_or_duplicate(db: Session, name: str) -> None:
    """Commit que transforma a violação da constraint em erro de negócio."""
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise DuplicatePantryItemError(name) from None
