"""Integração com o provedor de LLM (Gemini, via Google AI Studio).

Esta é a única parte do sistema que conhece o formato da API do provedor.
Trocar de provedor mexe neste arquivo e em nenhum outro — os routers só veem
`ask_llm(pergunta) -> str` e as exceções declaradas aqui.

A chave da API nunca sai deste módulo, nunca vai para log e nunca entra numa
resposta HTTP.
"""

import logging
import random
import time

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Timeouts separados: conectar é rápido, gerar texto não é. Um timeout único e
# generoso deixaria uma rede fora do ar pendurada pelo mesmo tempo que uma
# resposta longa e legítima.
TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)

# Status que o provedor devolve para congestionamento temporário. A própria
# mensagem do Gemini nesses casos diz "spikes in demand are usually temporary,
# please try again later" — ou seja, insistir é o comportamento pedido, não uma
# gambiarra. No plano gratuito eles aparecem com frequência.
RETRYABLE_STATUS = {429, 500, 503}

# Três tentativas, não mais: cada rodada extra atrasa a resposta de quem está
# esperando, e um provedor fora do ar não melhora na décima tentativa.
MAX_ATTEMPTS = 3

# Espera entre tentativas, dobrando a cada rodada. O jitter evita que vários
# usuários que falharam juntos voltem todos no mesmo instante e recriem o pico
# de demanda que causou o erro.
BACKOFF_BASE_SECONDS = 1.0
MAX_RETRY_AFTER_SECONDS = 10.0


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

    with httpx.Client(timeout=TIMEOUT) as client:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = client.post(
                    url,
                    json=payload,
                    # A chave vai no header, não em `?key=`. Query string
                    # aparece em log de servidor, de proxy e no header Referer —
                    # é o jeito mais fácil de vazar uma credencial sem perceber.
                    headers={"x-goog-api-key": settings.gemini_api_key},
                )
            except httpx.TimeoutException as exc:
                # Timeout não é retentado: o read timeout já é de 60s, e uma
                # segunda espera dessas estouraria o tempo que o navegador
                # aguarda — o usuário veria a aba travada em vez de um erro.
                raise LLMTimeoutError(str(exc)) from exc
            except httpx.HTTPError as exc:
                # str(exc) do httpx inclui a URL, mas nunca os headers — a chave
                # não aparece aqui. Ainda assim fica só no log do servidor.
                logger.warning("Falha de rede ao chamar o provedor de LLM: %s", exc)
                raise LLMUnavailableError(str(exc)) from exc

            if response.status_code == httpx.codes.OK:
                return _extract_text(response.json())

            # O corpo de erro do provedor vai para o log, não para a resposta
            # HTTP: ele pode conter detalhes de infraestrutura que não
            # interessam — nem convém expor — a quem está usando o chat.
            logger.warning(
                "Provedor de LLM respondeu %s (tentativa %s/%s): %s",
                response.status_code,
                attempt,
                MAX_ATTEMPTS,
                response.text[:500],
            )

            if response.status_code not in RETRYABLE_STATUS or attempt == MAX_ATTEMPTS:
                raise LLMUnavailableError(f"Provedor respondeu {response.status_code}.")

            time.sleep(_backoff_seconds(attempt, response))

    # Inalcançável: o laço ou retorna, ou levanta.
    raise LLMUnavailableError("O provedor não respondeu.")


def _backoff_seconds(attempt: int, response: httpx.Response) -> float:
    """Quanto esperar antes da próxima tentativa.

    Se o provedor disser explicitamente quanto esperar (`Retry-After`), essa
    informação vale mais que qualquer fórmula nossa — mas com um teto, para que
    um cabeçalho absurdo não prenda a requisição por minutos.
    """
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return min(float(retry_after), MAX_RETRY_AFTER_SECONDS)
        except ValueError:
            # Retry-After também pode vir como data HTTP; nesse caso ignoramos
            # e caímos no backoff exponencial.
            pass

    espera = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
    # O jitter evita que vários usuários que falharam juntos voltem no mesmo
    # instante e recriem o pico de demanda que causou o erro.
    return espera + random.uniform(0, 0.3)  # noqa: S311 — jitter, não criptografia


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
