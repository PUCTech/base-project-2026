"""Rotas de favoritos, avaliações e comentários de receitas."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.routers.recipes import NOT_FOUND
from app.schemas.recipe import CommentIn, CommentRead, RatingIn, RatingSummary
from app.services import recipe_social
from app.services.recipe_social import (
    CommentNotFoundError,
    NotCommentModeratorError,
    OwnRecipeRatingError,
    RatingStats,
)
from app.services.recipes import RecipeNotFoundError

router = APIRouter(prefix="/recipes", tags=["recipes"])


# ---------- Favoritos ----------


@router.put(
    "/{recipe_id}/favorite",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Marca a receita como favorita",
)
def favorite(
    recipe_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    try:
        recipe_social.add_favorite(db, current_user.id, recipe_id)
    except RecipeNotFoundError:
        raise NOT_FOUND from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{recipe_id}/favorite",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Desmarca a receita como favorita",
)
def unfavorite(
    recipe_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    try:
        recipe_social.remove_favorite(db, current_user.id, recipe_id)
    except RecipeNotFoundError:
        raise NOT_FOUND from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Avaliações ----------


def _rating_summary(db: Session, user_id: int, recipe_id: int) -> RatingSummary:
    stats = recipe_social.rating_stats(db, [recipe_id]).get(recipe_id, RatingStats(None, 0))
    return RatingSummary(
        avg_rating=stats.average,
        rating_count=stats.count,
        my_rating=recipe_social.my_rating(db, user_id, recipe_id),
    )


@router.put(
    "/{recipe_id}/rating",
    response_model=RatingSummary,
    summary="Dá ou altera a nota da receita",
)
def rate_recipe(
    recipe_id: int,
    data: RatingIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RatingSummary:
    try:
        recipe_social.rate(db, current_user.id, recipe_id, data.stars)
    except RecipeNotFoundError:
        raise NOT_FOUND from None
    except OwnRecipeRatingError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Não é possível avaliar a própria receita",
        ) from None
    return _rating_summary(db, current_user.id, recipe_id)


@router.delete(
    "/{recipe_id}/rating",
    response_model=RatingSummary,
    summary="Remove a própria nota",
)
def unrate_recipe(
    recipe_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RatingSummary:
    try:
        recipe_social.remove_rating(db, current_user.id, recipe_id)
    except RecipeNotFoundError:
        raise NOT_FOUND from None
    return _rating_summary(db, current_user.id, recipe_id)


# ---------- Comentários ----------


@router.get(
    "/{recipe_id}/comments",
    response_model=list[CommentRead],
    summary="Comentários da receita, do mais antigo ao mais novo",
)
def read_comments(
    recipe_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CommentRead]:
    try:
        return recipe_social.list_comments(db, recipe_id)
    except RecipeNotFoundError:
        raise NOT_FOUND from None


@router.post(
    "/{recipe_id}/comments",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Comenta a receita",
)
def comment(
    recipe_id: int,
    data: CommentIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CommentRead:
    try:
        return recipe_social.add_comment(db, current_user.id, recipe_id, data.content)
    except RecipeNotFoundError:
        raise NOT_FOUND from None


@router.delete(
    "/{recipe_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Remove um comentário (autor do comentário ou da receita)",
)
def remove_comment(
    recipe_id: int,
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    try:
        recipe_social.delete_comment(db, current_user.id, recipe_id, comment_id)
    except (RecipeNotFoundError, CommentNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comentário não encontrado"
        ) from None
    except NotCommentModeratorError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Só quem escreveu ou o autor da receita pode remover o comentário",
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
