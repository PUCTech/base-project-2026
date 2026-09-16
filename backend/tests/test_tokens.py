"""Testes de emissão e validação do JWT."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.config import get_settings
from app.services.tokens import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
)

settings = get_settings()


def test_token_emitido_devolve_o_user_id():
    token, _ = create_access_token(42)
    assert decode_access_token(token) == 42


def test_token_declara_o_prazo_de_expiracao():
    _, expires_in = create_access_token(1)
    assert expires_in == settings.access_token_expire_minutes * 60


def test_token_malformado_e_recusado():
    with pytest.raises(InvalidTokenError):
        decode_access_token("isto-nao-e-um-token")


def test_assinatura_adulterada_e_recusada():
    token, _ = create_access_token(1)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token[:-4] + "AAAA")


def test_token_assinado_com_outra_chave_e_recusado():
    forjado = jwt.encode(
        {"sub": "1", "exp": datetime.now(UTC) + timedelta(hours=1)},
        "chave-do-atacante",
        algorithm="HS256",
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(forjado)


def test_token_sem_assinatura_e_recusado():
    """A falha clássica do JWT: aceitar o algoritmo que o próprio token declara.
    Quem faz isso aceita `alg: none` e deixa qualquer um assinar tokens."""
    forjado = jwt.encode(
        {"sub": "1", "exp": 9999999999}, "", algorithm="none"
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(forjado)


def test_token_expirado_e_recusado():
    expirado = jwt.encode(
        {
            "sub": "1",
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "exp": datetime.now(UTC) - timedelta(hours=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(expirado)


def test_token_sem_exp_e_recusado():
    """Um token sem prazo seria válido para sempre."""
    sem_exp = jwt.encode(
        {"sub": "1"}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(sem_exp)
