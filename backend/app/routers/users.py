"""CRUD do próprio usuário.

Todas as rotas operam sobre `/me`: o usuário vem do token, nunca de um id na
URL. Não existe `PATCH /users/{id}` aqui de propósito — uma rota assim exige
verificar, a cada chamada, se o id pertence a quem está autenticado, e é
exatamente esse tipo de verificação que se esquece de fazer.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas.user import UserRead, UserUpdate
from app.services import storage
from app.services.recipes import image_filenames_by_author
from app.services.users import UsernameAlreadyExistsError, delete_user, update_user

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=UserRead, summary="Atualiza o próprio usuário")
def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserRead:
    try:
        return update_user(db, current_user, data)
    except UsernameAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este nome de usuário já está em uso",
        ) from None


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Remove a própria conta",
)
def delete_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    # As linhas das receitas somem por cascata no banco, mas os arquivos das
    # fotos estão fora dele: a lista é lida antes e apagada depois do commit.
    images = image_filenames_by_author(db, current_user.id)
    delete_user(db, current_user)
    for image in images:
        storage.delete_recipe_image(image)
    # 204 não tem corpo. Tokens já emitidos continuam válidos até expirar:
    # é a contrapartida de uma sessão sem estado no servidor. Aqui isso não
    # dá acesso a nada, porque get_current_user não encontra mais o usuário.
    return Response(status_code=status.HTTP_204_NO_CONTENT)
