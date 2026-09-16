"""Dependências compartilhadas pelos routers."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services.tokens import InvalidTokenError, decode_access_token
from app.services.users import get_user_by_id

# auto_error=False de propósito.
#
# Com auto_error=True o FastAPI responde 403 quando o header Authorization
# falta ou usa outro esquema — e 403 é a resposta errada: pela RFC 7235, 401 é
# "não sei quem você é" e 403 é "sei quem você é, e você não pode". Quem chega
# sem token está no primeiro caso.
#
# Desligando o erro automático, todos os caminhos de falha passam pela mesma
# resposta abaixo, e o cliente não consegue distinguir "faltou token" de "token
# expirado" de "conta apagada".
bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciais inválidas ou expiradas",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve o usuário autenticado a partir do token.

    Toda rota protegida recebe o usuário por aqui. É o que garante que o
    `user_id` venha sempre do token assinado, e nunca do corpo ou da query
    string da requisição — caso contrário bastaria trocar um número no JSON
    para ler ou alterar os dados de outra conta.
    """
    if credentials is None:
        raise _UNAUTHORIZED

    try:
        user_id = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        raise _UNAUTHORIZED from None

    user = get_user_by_id(db, user_id)
    if user is None:
        # Token com assinatura válida, mas a conta foi apagada depois da
        # emissão. O token continua criptograficamente íntegro e mesmo assim
        # não deve dar acesso a nada.
        raise _UNAUTHORIZED

    return user
