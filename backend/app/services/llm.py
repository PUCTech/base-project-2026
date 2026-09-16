"""Integração com o provedor de LLM (Gemini, via Google AI Studio).

Esta é a única parte do sistema que conhece o formato da API do provedor.
Trocar de provedor mexe neste arquivo e em nenhum outro — os routers só veem
`ask_llm(pergunta) -> str` e as exceções declaradas aqui.

A chave da API nunca sai deste módulo, nunca vai para log e nunca entra numa
resposta HTTP.
"""

import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Timeouts separados: conectar é rápido, gerar texto não é. Um timeout único e
# generoso deixaria uma rede fora do ar pendurada pelo mesmo tempo que uma
# resposta longa e legítima.
TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)


class LLMNotConfiguredError(Exception):
    """GEMINI_API_KEY não foi definida no ambiente."""


class LLMTimeoutError(Exception):
    """O provedor não respondeu dentro do tempo limite."""


class LLMUnavailableError(Exception):
    """O provedor falhou ou respondeu fora do contrato."""


class ContentBlockedError(Exception):
    """O provedor recusou a pergunta por filtro de conteúdo."""


def ask_llm(question: str) -> str:
    """Envia a pergunta ao modelo e devolve o texto da resposta."""
    if not settings.gemini_api_key:
        raise LLMNotConfiguredError(
            "GEMINI_API_KEY não está definida no ambiente do backend."
        )

    url = f"{BASE_URL}/models/{settings.gemini_model}:generateContent"
    payload = {"contents": [{"parts": [{"text": question}]}]}

    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.post(
                url,
                json=payload,
                # A chave vai no header, não em `?key=`. Query string aparece em
                # log de servidor, de proxy e no header Referer — é o jeito mais
                # fácil de vazar uma credencial sem perceber.
                headers={"x-goog-api-key": settings.gemini_api_key},
            )
    except httpx.TimeoutException as exc:
        raise LLMTimeoutError(str(exc)) from exc
    except httpx.HTTPError as exc:
        # str(exc) do httpx inclui a URL, mas nunca os headers — a chave não
        # aparece aqui. Ainda assim a mensagem fica só no log do servidor.
        logger.warning("Falha de rede ao chamar o provedor de LLM: %s", exc)
        raise LLMUnavailableError(str(exc)) from exc

    if response.status_code != httpx.codes.OK:
        # O corpo de erro do provedor vai para o log, não para a resposta HTTP:
        # ele pode conter detalhes de infraestrutura que não interessam — nem
        # convém expor — a quem está usando o chat.
        logger.warning(
            "Provedor de LLM respondeu %s: %s", response.status_code, response.text[:500]
        )
        raise LLMUnavailableError(f"Provedor respondeu {response.status_code}.")

    return _extract_text(response.json())


def _extract_text(body: dict) -> str:
    """Tira o texto da resposta do Gemini, validando o formato.

    A estrutura é aninhada e cada nível pode faltar. Navegar com `body[...]`
    direto transformaria uma resposta inesperada em KeyError e, no fim,
    em um 500 — quando o certo é dizer que foi o provedor que falhou.
    """
    candidates = body.get("candidates")

    if not candidates:
        # Sem candidatos costuma significar prompt barrado pelo filtro.
        reason = (body.get("promptFeedback") or {}).get("blockReason")
        if reason:
            raise ContentBlockedError(str(reason))
        raise LLMUnavailableError("O provedor respondeu sem nenhum candidato.")

    candidate = candidates[0]

    if candidate.get("finishReason") == "SAFETY":
        raise ContentBlockedError("SAFETY")

    parts = (candidate.get("content") or {}).get("parts") or []
    text = "".join(part.get("text", "") for part in parts).strip()

    if not text:
        raise LLMUnavailableError("O provedor respondeu sem texto.")

    return text
