"""Favoritos, avaliações e comentários de receitas."""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import RecipeComment, RecipeFavorite, RecipeRating
from app.services.recipes import get_recipe


class OwnRecipeRatingError(Exception):
    """O autor tentou avaliar a própria receita."""


class CommentNotFoundError(Exception):
    """O comentário não existe nesta receita."""


class NotCommentModeratorError(Exception):
    """Quem pediu não é autor do comentário nem da receita."""


# ---------- Favoritos ----------


def add_favorite(db: Session, user_id: int, recipe_id: int) -> None:
    """Idempotente: favoritar o que já é favorito não é erro.

    PUT e DELETE em vez de um "toggle": se a requisição for repetida (clique
    duplo, retentativa de rede), o resultado continua sendo o que o usuário
    pediu, e não o contrário.
    """
    get_recipe(db, recipe_id)
    if db.get(RecipeFavorite, (user_id, recipe_id)) is not None:
        return
    db.add(RecipeFavorite(user_id=user_id, recipe_id=recipe_id))
    try:
        db.commit()
    except IntegrityError:
        # Duas requisições simultâneas passaram pela conferência acima; a
        # chave primária barrou a segunda. O estado final é o pedido.
        db.rollback()


def remove_favorite(db: Session, user_id: int, recipe_id: int) -> None:
    get_recipe(db, recipe_id)
    favorite = db.get(RecipeFavorite, (user_id, recipe_id))
    if favorite is not None:
        db.delete(favorite)
        db.commit()


def favorite_ids(db: Session, user_id: int, recipe_ids: Sequence[int]) -> set[int]:
    if not recipe_ids:
        return set()
    return set(
        db.scalars(
            select(RecipeFavorite.recipe_id).where(
                RecipeFavorite.user_id == user_id, RecipeFavorite.recipe_id.in_(recipe_ids)
            )
        )
    )


# ---------- Avaliações ----------


@dataclass(frozen=True)
class RatingStats:
    average: float | None
    count: int


def rate(db: Session, user_id: int, recipe_id: int, stars: int) -> None:
    """Cria ou atualiza a nota do usuário (upsert)."""
    recipe = get_recipe(db, recipe_id)
    if recipe.author_id == user_id:
        raise OwnRecipeRatingError(recipe_id)

    rating = db.get(RecipeRating, (user_id, recipe_id))
    if rating is None:
        db.add(RecipeRating(user_id=user_id, recipe_id=recipe_id, stars=stars))
    else:
        rating.stars = stars
    db.commit()


def remove_rating(db: Session, user_id: int, recipe_id: int) -> None:
    get_recipe(db, recipe_id)
    rating = db.get(RecipeRating, (user_id, recipe_id))
    if rating is not None:
        db.delete(rating)
        db.commit()


def rating_stats(db: Session, recipe_ids: Sequence[int]) -> dict[int, RatingStats]:
    """Média e total de notas de várias receitas, numa consulta só.

    A média é calculada na hora, e não guardada numa coluna da receita. Guardar
    seria mais rápido de ler, mas exigiria manter os dois valores sincronizados
    a cada nota — e um contador dessincronizado é um bug silencioso. Com o
    volume deste projeto, calcular custa nada.
    """
    if not recipe_ids:
        return {}
    rows = db.execute(
        select(RecipeRating.recipe_id, func.avg(RecipeRating.stars), func.count())
        .where(RecipeRating.recipe_id.in_(recipe_ids))
        .group_by(RecipeRating.recipe_id)
    )
    return {
        recipe_id: RatingStats(average=round(float(average), 1), count=count)
        for recipe_id, average, count in rows
    }


def my_rating(db: Session, user_id: int, recipe_id: int) -> int | None:
    rating = db.get(RecipeRating, (user_id, recipe_id))
    return rating.stars if rating else None


# ---------- Comentários ----------


def list_comments(db: Session, recipe_id: int) -> list[RecipeComment]:
    get_recipe(db, recipe_id)
    return list(
        db.scalars(
            select(RecipeComment)
            .options(selectinload(RecipeComment.author))
            .where(RecipeComment.recipe_id == recipe_id)
            .order_by(RecipeComment.created_at, RecipeComment.id)
        )
    )


def add_comment(db: Session, user_id: int, recipe_id: int, content: str) -> RecipeComment:
    get_recipe(db, recipe_id)
    comment = RecipeComment(recipe_id=recipe_id, author_id=user_id, content=content)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


def delete_comment(db: Session, user_id: int, recipe_id: int, comment_id: int) -> None:
    """Apaga o comentário. Pode quem escreveu e pode o autor da receita.

    Dois papéis com o mesmo poder sobre o mesmo recurso: o autor do comentário
    porque o texto é dele, o autor da receita porque a página é dele
    (moderação).
    """
    recipe = get_recipe(db, recipe_id)
    # O comentário precisa pertencer à receita da URL. Sem essa checagem,
    # DELETE /recipes/1/comments/50 apagaria o comentário 50 mesmo que ele
    # fosse da receita 7 — e a regra de moderação acima seria contornada
    # usando uma receita sua na URL.
    comment = db.scalar(
        select(RecipeComment).where(
            RecipeComment.id == comment_id, RecipeComment.recipe_id == recipe_id
        )
    )
    if comment is None:
        raise CommentNotFoundError(comment_id)
    if user_id not in (comment.author_id, recipe.author_id):
        raise NotCommentModeratorError(comment_id)

    db.delete(comment)
    db.commit()
