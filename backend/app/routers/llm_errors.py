"""Tradução das falhas do LLM para respostas HTTP.

Toda rota que chama o modelo — o chat e as funções de IA da cozinha — precisa
responder do mesmo jeito quando o provedor falha. Concentrar o mapeamento aqui
evita que cada router invente seu próprio status code para o mesmo problema.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException, status

from app.services.llm import (
    ContentBlockedError,
    LLMNotConfiguredError,
    LLMTimeoutError,
    LLMUnavailableError,
)


@contextmanager
def llm_errors_as_http() -> Iterator[None]:
    """Converte as exceções do serviço de LLM em `HTTPException`.

    Uso:
        with llm_errors_as_http():
            reply = ask_llm(...)
    """
    try:
        yield
    except LLMNotConfiguredError:
        # Erro de operação, não do usuário: a aplicação subiu sem a chave.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="O serviço de IA não está configurado no servidor.",
        ) from None
    except LLMTimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="O serviço de IA demorou demais para responder. Tente novamente.",
        ) from None
    except ContentBlockedError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A pergunta foi recusada pelo filtro de conteúdo do provedor.",
        ) from None
    except LLMUnavailableError:
        # A causa detalhada já foi para o log do servidor. A resposta HTTP fica
        # genérica de propósito: mensagens de erro do provedor podem conter
        # detalhes de infraestrutura que não interessam a quem usa o chat.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="O serviço de IA está indisponível. Tente novamente em instantes.",
        ) from None
