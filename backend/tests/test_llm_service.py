"""Testes do serviço de LLM.

Nenhum teste aqui toca a rede. O httpx é interceptado por um MockTransport, o
que permite exercitar timeout, erro 500 e resposta fora do formato — situações
que não dá para provocar de propósito contra o provedor real, e que são
justamente as que quebram em produção.
"""

import httpx
import pytest

from app.services import llm
from app.services.llm import (
    ContentBlockedError,
    LLMNotConfiguredError,
    LLMTimeoutError,
    LLMUnavailableError,
    ask_llm,
)

RESPOSTA_OK = {
    "candidates": [{"content": {"parts": [{"text": "  Uma resposta do modelo.  "}]}}]
}


@pytest.fixture(autouse=True)
def chave_configurada(monkeypatch):
    """Toda chamada precisa de uma chave; esta é falsa e nunca sai do processo."""
    monkeypatch.setattr(llm.settings, "gemini_api_key", "chave-de-teste")
    monkeypatch.setattr(llm.settings, "gemini_model", "gemini-2.0-flash")


def usar_transporte(monkeypatch, handler):
    """Faz o httpx.Client responder pelo handler, sem sair para a rede."""
    original = httpx.Client

    def client_fake(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original(*args, **kwargs)

    monkeypatch.setattr(llm.httpx, "Client", client_fake)


def test_devolve_o_texto_da_resposta(monkeypatch):
    usar_transporte(monkeypatch, lambda request: httpx.Response(200, json=RESPOSTA_OK))
    assert ask_llm("Olá?") == "Uma resposta do modelo."


def test_a_chave_vai_no_header_e_nao_na_url(monkeypatch):
    """Chave em query string vaza em log de servidor, de proxy e no Referer."""
    capturado = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["url"] = str(request.url)
        capturado["header"] = request.headers.get("x-goog-api-key")
        return httpx.Response(200, json=RESPOSTA_OK)

    usar_transporte(monkeypatch, handler)
    ask_llm("Olá?")

    assert capturado["header"] == "chave-de-teste"
    assert "chave-de-teste" not in capturado["url"]
    assert "key=" not in capturado["url"]


def test_a_pergunta_chega_no_corpo(monkeypatch):
    capturado = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["body"] = request.content.decode()
        return httpx.Response(200, json=RESPOSTA_OK)

    usar_transporte(monkeypatch, handler)
    ask_llm("Qual a capital da França?")

    assert "Qual a capital da França?" in capturado["body"]


def test_sem_chave_configurada_levanta_erro_proprio(monkeypatch):
    monkeypatch.setattr(llm.settings, "gemini_api_key", "")
    with pytest.raises(LLMNotConfiguredError):
        ask_llm("Olá?")


def test_timeout_vira_erro_de_timeout(monkeypatch):
    def handler(request):
        raise httpx.ReadTimeout("demorou demais", request=request)

    usar_transporte(monkeypatch, handler)
    with pytest.raises(LLMTimeoutError):
        ask_llm("Olá?")


def test_erro_de_rede_vira_indisponivel(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("sem rota para o host", request=request)

    usar_transporte(monkeypatch, handler)
    with pytest.raises(LLMUnavailableError):
        ask_llm("Olá?")


@pytest.mark.parametrize("status_code", [400, 401, 429, 500, 503])
def test_status_de_erro_do_provedor_vira_indisponivel(monkeypatch, status_code):
    usar_transporte(
        monkeypatch, lambda request: httpx.Response(status_code, json={"error": "x"})
    )
    with pytest.raises(LLMUnavailableError):
        ask_llm("Olá?")


def test_prompt_barrado_pelo_filtro(monkeypatch):
    usar_transporte(
        monkeypatch,
        lambda request: httpx.Response(
            200, json={"promptFeedback": {"blockReason": "SAFETY"}}
        ),
    )
    with pytest.raises(ContentBlockedError):
        ask_llm("algo barrado")


def test_resposta_interrompida_por_seguranca(monkeypatch):
    usar_transporte(
        monkeypatch,
        lambda request: httpx.Response(
            200, json={"candidates": [{"finishReason": "SAFETY", "content": {}}]}
        ),
    )
    with pytest.raises(ContentBlockedError):
        ask_llm("algo barrado")


@pytest.mark.parametrize(
    "corpo",
    [
        {},
        {"candidates": []},
        {"candidates": [{}]},
        {"candidates": [{"content": {}}]},
        {"candidates": [{"content": {"parts": []}}]},
        {"candidates": [{"content": {"parts": [{"text": "   "}]}}]},
    ],
    ids=["vazio", "sem-candidatos", "sem-content", "sem-parts", "parts-vazio", "texto-branco"],
)
def test_resposta_fora_do_formato_vira_indisponivel(monkeypatch, corpo):
    """Navegar a resposta com body[...] direto viraria KeyError e, no fim, um
    500 — quando o certo é dizer que quem falhou foi o provedor."""
    usar_transporte(monkeypatch, lambda request: httpx.Response(200, json=corpo))
    with pytest.raises(LLMUnavailableError):
        ask_llm("Olá?")


def test_partes_multiplas_sao_concatenadas(monkeypatch):
    usar_transporte(
        monkeypatch,
        lambda request: httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "Parte 1. "}, {"text": "Parte 2."}]}}]},
        ),
    )
    assert ask_llm("Olá?") == "Parte 1. Parte 2."
