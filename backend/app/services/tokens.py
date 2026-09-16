"""Emissão e validação do JWT que carrega a sessão.

O token é *assinado*, não criptografado: qualquer pessoa consegue ler o payload
(é base64, não segredo). O que a assinatura garante é que ninguém conseguiu
*alterar* o conteúdo sem a chave. Daí a regra prática: nada sensível vai dentro
do token — só o id do usuário e os prazos.
"""

from datetime import UTC, datetime, timedelta

import jwt

from app.config import get_settings

settings = get_settings()


class InvalidTokenError(Exception):
    """Token ausente, malformado, expirado ou com assinatura inválida."""


def create_access_token(user_id: int) -> tuple[str, int]:
    """Devolve `(token, segundos_até_expirar)` para o usuário informado."""
    expires_in = settings.access_token_expire_minutes * 60
    now = datetime.now(UTC)

    payload = {
        # `sub` é string por exigência da RFC 7519. PyJWT 2.10+ rejeita um
        # `sub` numérico na validação, então o int vira str na emissão.
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }

    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expires_in


def decode_access_token(token: str) -> int:
    """Valida o token e devolve o `user_id`.

    O algoritmo é passado como lista fechada. Aceitar o algoritmo que o próprio
    token declara é a falha clássica do JWT: um atacante troca o header para
    `alg: none` (ou para HMAC, usando a chave pública como segredo) e passa a
    assinar tokens sozinho.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    try:
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidTokenError("O campo 'sub' não é um id de usuário.") from exc
