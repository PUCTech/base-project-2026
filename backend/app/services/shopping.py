"""Regra de negócio da lista de compras.

A lista fecha o ciclo da cozinha: a receita diz o que falta, o que falta vai
para a lista, e o que foi comprado volta para a despensa.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PantryItem, Recipe, ShoppingItem
from app.schemas.pantry import PantryItemCreate
from app.schemas.shopping import ShoppingItemIn, ShoppingItemUpdate, ShoppingSource
from app.services.ingredients import convert, ingredient_key, shortfalls
from app.services.pantry import list_pantry, merge_into_pantry


class ShoppingItemNotFoundError(Exception):
    """O item não existe — ou existe, mas é de outro usuário."""


def list_items(db: Session, user_id: int) -> list[ShoppingItem]:
    # O que falta comprar primeiro, agrupado por categoria — a ordem em que se
    # anda pelo mercado. O que já está no carrinho vai para o fim.
    return list(
        db.scalars(
            select(ShoppingItem)
            .where(ShoppingItem.user_id == user_id)
            .order_by(
                ShoppingItem.checked, ShoppingItem.category, ShoppingItem.name_key, ShoppingItem.id
            )
        )
    )


def get_item(db: Session, user_id: int, item_id: int) -> ShoppingItem:
    item = db.scalar(
        select(ShoppingItem).where(ShoppingItem.id == item_id, ShoppingItem.user_id == user_id)
    )
    if item is None:
        raise ShoppingItemNotFoundError(item_id)
    return item


def add_items(
    db: Session,
    user_id: int,
    entries: Iterable[ShoppingItemIn],
    *,
    source: ShoppingSource,
    recipe_id: int | None = None,
) -> int:
    """Adiciona itens à lista, juntando com os que ainda não foram comprados.

    Todo caminho de escrita na lista passa por aqui: o formulário, o "o que
    falta na receita" e a sugestão da IA. Duas receitas que pedem ovos viram
    uma linha com a soma, e não duas linhas de ovos. Devolve quantos itens
    foram processados.
    """
    count = 0
    for entry in entries:
        _add_one(db, user_id, entry, source=source, recipe_id=recipe_id)
        db.flush()  # para o próximo item do lote enxergar este
        count += 1
    db.commit()
    return count


def _add_one(
    db: Session,
    user_id: int,
    entry: ShoppingItemIn,
    *,
    source: ShoppingSource,
    recipe_id: int | None,
) -> None:
    name_key = ingredient_key(entry.name)
    pending = db.scalars(
        select(ShoppingItem).where(
            ShoppingItem.user_id == user_id,
            ShoppingItem.name_key == name_key,
            ShoppingItem.checked.is_(False),
        )
    ).all()

    for item in pending:
        if item.quantity is None or entry.quantity is None:
            # "Comprar sal" já cobre "comprar 5 g de sal".
            return
        added = convert(entry.quantity, entry.unit, item.unit)
        if added is not None:
            item.quantity = round(item.quantity + added, 3)
            return

    # Nada para juntar — ou só itens em unidades incomparáveis ("3 un" e
    # "500 g" de tomate). Numa lista de compras, duas linhas são mais honestas
    # que um total inventado.
    db.add(
        ShoppingItem(
            user_id=user_id,
            name_key=name_key,
            source=source,
            recipe_id=recipe_id,
            **entry.model_dump(),
        )
    )


def update_item(
    db: Session, user_id: int, item_id: int, data: ShoppingItemUpdate
) -> ShoppingItem:
    item = get_item(db, user_id, item_id)
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes:
        item.name_key = ingredient_key(changes["name"])
    for field, value in changes.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, user_id: int, item_id: int) -> None:
    db.delete(get_item(db, user_id, item_id))
    db.commit()


def clear_checked(db: Session, user_id: int) -> None:
    """Descarta os marcados sem levar para a despensa."""
    for item in _checked(db, user_id):
        db.delete(item)
    db.commit()


@dataclass(frozen=True)
class _Needed:
    name: str
    quantity: float | None
    unit: str | None


def add_missing_from_recipe(
    db: Session, user_id: int, recipe: Recipe, servings: int | None = None
) -> int:
    """Põe na lista o que falta na despensa para fazer a receita.

    `servings` ajusta as quantidades: a receita rende 2, mas hoje vão ser 4.
    """
    factor = servings / recipe.servings if servings else 1
    needed = [
        _Needed(
            name=ingredient.name,
            quantity=ingredient.quantity * factor if ingredient.quantity else None,
            unit=ingredient.unit,
        )
        for ingredient in recipe.ingredients
    ]
    missing = shortfalls(needed, list_pantry(db, user_id))

    return add_items(
        db,
        user_id,
        (
            ShoppingItemIn(
                name=s.name,
                quantity=round(s.quantity, 2) if s.quantity else None,
                unit=s.unit,
            )
            for s in missing
        ),
        source="receita",
        recipe_id=recipe.id,
    )


def checkout(db: Session, user_id: int) -> tuple[int, list[PantryItem]]:
    """Leva os itens marcados para a despensa e os tira da lista.

    Uma transação só: ou a despensa recebe tudo e a lista se esvazia, ou nada
    muda. Uma falha no meio que deixasse o item nos dois lugares — ou em
    nenhum — seria pior que a falha em si.
    """
    bought = _checked(db, user_id)
    merge_into_pantry(
        db,
        user_id,
        (
            PantryItemCreate(
                name=item.name, quantity=item.quantity, unit=item.unit, category=item.category
            )
            for item in bought
        ),
    )
    for item in bought:
        db.delete(item)
    db.commit()
    return len(bought), list_pantry(db, user_id)


def _checked(db: Session, user_id: int) -> list[ShoppingItem]:
    return list(
        db.scalars(
            select(ShoppingItem).where(
                ShoppingItem.user_id == user_id, ShoppingItem.checked.is_(True)
            )
        )
    )
