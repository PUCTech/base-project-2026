"""Testes do serviço de LLM.

Nenhum teste aqui toca a rede. O httpx é interceptado por um MockTransport, o
que permite exercitar timeout, erro 500 e resposta fora do formato — situações
que não dá para provocar de propósito contra o provedor real, e que são
justamente as que quebram em produção.
"""

import json

import httpx
import pytest

from app.services import llm
from app.services.llm import (
    ChatTurn,
    ContentBlockedError,
    LLMNotConfiguredError,
    LLMTimeoutError,
    LLMUnavailableError,
    ask_llm,
    ask_llm_json,
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


class TestRetentativa:
    """O provedor devolve 503 'high demand' com frequência no plano gratuito, e
    a própria mensagem pede para tentar de novo. Estes testes fixam quantas
    vezes insistimos e quando desistimos."""

    @pytest.fixture(autouse=True)
    def sem_espera_real(self, monkeypatch):
        """Neutraliza o backoff: o teste verifica a lógica, não o relógio."""
        monkeypatch.setattr(llm.time, "sleep", lambda segundos: None)

    def test_503_seguido_de_sucesso_devolve_a_resposta(self, monkeypatch):
        tentativas = []

        def handler(request):
            tentativas.append(1)
            if len(tentativas) == 1:
                return httpx.Response(503, json={"error": "high demand"})
            return httpx.Response(200, json=RESPOSTA_OK)

        usar_transporte(monkeypatch, handler)

        assert ask_llm("Olá?") == "Uma resposta do modelo."
        assert len(tentativas) == 2

    def test_desiste_apos_o_limite_de_tentativas(self, monkeypatch):
        tentativas = []

        def handler(request):
            tentativas.append(1)
            return httpx.Response(503, json={"error": "high demand"})

        usar_transporte(monkeypatch, handler)

        with pytest.raises(LLMUnavailableError):
            ask_llm("Olá?")
        assert len(tentativas) == llm.MAX_ATTEMPTS

    @pytest.mark.parametrize("status_code", sorted(llm.RETRYABLE_STATUS))
    def test_status_temporarios_sao_retentados(self, monkeypatch, status_code):
        tentativas = []

        def handler(request):
            tentativas.append(1)
            return httpx.Response(status_code, json={"error": "x"})

        usar_transporte(monkeypatch, handler)

        with pytest.raises(LLMUnavailableError):
            ask_llm("Olá?")
        assert len(tentativas) == llm.MAX_ATTEMPTS

    @pytest.mark.parametrize("status_code", [400, 401, 403, 404])
    def test_erro_permanente_nao_e_retentado(self, monkeypatch, status_code):
        """Chave inválida ou modelo inexistente não melhoram na segunda
        tentativa — insistir só atrasaria a resposta de erro."""
        tentativas = []

        def handler(request):
            tentativas.append(1)
            return httpx.Response(status_code, json={"error": "x"})

        usar_transporte(monkeypatch, handler)

        with pytest.raises(LLMUnavailableError):
            ask_llm("Olá?")
        assert len(tentativas) == 1

    def test_timeout_nao_e_retentado(self, monkeypatch):
        """O read timeout já é de 60s; uma segunda espera estouraria o tempo que
        o navegador aguarda, e o usuário veria a aba travada em vez de um erro."""
        tentativas = []

        def handler(request):
            tentativas.append(1)
            raise httpx.ReadTimeout("demorou", request=request)

        usar_transporte(monkeypatch, handler)

        with pytest.raises(LLMTimeoutError):
            ask_llm("Olá?")
        assert len(tentativas) == 1

    def test_respeita_o_retry_after_do_provedor(self, monkeypatch):
        esperas = []
        monkeypatch.setattr(llm.time, "sleep", lambda s: esperas.append(s))

        usar_transporte(
            monkeypatch,
            lambda request: httpx.Response(503, headers={"Retry-After": "2"}, json={}),
        )

        with pytest.raises(LLMUnavailableError):
            ask_llm("Olá?")
        assert esperas == [2.0, 2.0]

    def test_retry_after_absurdo_e_limitado(self, monkeypatch):
        """Um cabeçalho de uma hora não pode prender a requisição."""
        esperas = []
        monkeypatch.setattr(llm.time, "sleep", lambda s: esperas.append(s))

        usar_transporte(
            monkeypatch,
            lambda request: httpx.Response(503, headers={"Retry-After": "3600"}, json={}),
        )

        with pytest.raises(LLMUnavailableError):
            ask_llm("Olá?")
        assert all(e <= llm.MAX_RETRY_AFTER_SECONDS for e in esperas)

    def test_retry_after_em_formato_de_data_cai_no_backoff(self, monkeypatch):
        """Retry-After também pode vir como data HTTP; nesse caso ignoramos."""
        esperas = []
        monkeypatch.setattr(llm.time, "sleep", lambda s: esperas.append(s))

        usar_transporte(
            monkeypatch,
            lambda request: httpx.Response(
                503, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}, json={}
            ),
        )

        with pytest.raises(LLMUnavailableError):
            ask_llm("Olá?")
        # Backoff exponencial: a segunda espera é maior que a primeira.
        assert len(esperas) == 2
        assert esperas[1] > esperas[0]

    def test_o_backoff_cresce_a_cada_tentativa(self, monkeypatch):
        esperas = []
        monkeypatch.setattr(llm.time, "sleep", lambda s: esperas.append(s))

        usar_transporte(monkeypatch, lambda request: httpx.Response(503, json={}))

        with pytest.raises(LLMUnavailableError):
            ask_llm("Olá?")
        assert esperas[0] >= llm.BACKOFF_BASE_SECONDS
        assert esperas[1] >= llm.BACKOFF_BASE_SECONDS * 2


class TestContextoDaConversa:
    """Histórico e instrução de sistema chegam ao provedor no formato dele."""

    def capturar_corpo(self, monkeypatch) -> dict:
        capturado: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            capturado.update(json.loads(request.content))
            return httpx.Response(200, json=RESPOSTA_OK)

        usar_transporte(monkeypatch, handler)
        return capturado

    def test_sem_contexto_envia_so_a_pergunta(self, monkeypatch):
        corpo = self.capturar_corpo(monkeypatch)
        ask_llm("Olá?")

        assert corpo["contents"] == [{"role": "user", "parts": [{"text": "Olá?"}]}]
        assert "systemInstruction" not in corpo

    def test_historico_vem_antes_da_pergunta_com_papeis_do_provedor(self, monkeypatch):
        """'assistant' é vocabulário nosso; o Gemini chama esse papel de 'model'."""
        corpo = self.capturar_corpo(monkeypatch)
        ask_llm(
            "E com frango?",
            history=[
                ChatTurn(role="user", content="Uma receita com arroz?"),
                ChatTurn(role="assistant", content="Arroz de forno."),
            ],
        )

        assert [c["role"] for c in corpo["contents"]] == ["user", "model", "user"]
        assert corpo["contents"][-1]["parts"][0]["text"] == "E com frango?"

    def test_instrucao_de_sistema_fica_separada_das_falas(self, monkeypatch):
        corpo = self.capturar_corpo(monkeypatch)
        ask_llm("Olá?", system_instruction="Você é um assistente de cozinha.")

        assert corpo["systemInstruction"]["parts"][0]["text"] == "Você é um assistente de cozinha."
        assert all("assistente de cozinha" not in str(c) for c in corpo["contents"])


class TestRespostaEmJson:
    SCHEMA = {"type": "OBJECT", "properties": {"nome": {"type": "STRING"}}}

    def responder_texto(self, monkeypatch, texto: str) -> dict:
        capturado: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            capturado.update(json.loads(request.content))
            return httpx.Response(
                200, json={"candidates": [{"content": {"parts": [{"text": texto}]}}]}
            )

        usar_transporte(monkeypatch, handler)
        return capturado

    def test_devolve_o_json_ja_decodificado(self, monkeypatch):
        self.responder_texto(monkeypatch, '{"nome": "Bolo de cenoura"}')
        assert ask_llm_json("Uma receita", response_schema=self.SCHEMA) == {
            "nome": "Bolo de cenoura"
        }

    def test_pede_json_e_envia_o_schema(self, monkeypatch):
        corpo = self.responder_texto(monkeypatch, "{}")
        ask_llm_json("Uma receita", response_schema=self.SCHEMA)

        config = corpo["generationConfig"]
        assert config["responseMimeType"] == "application/json"
        assert config["responseSchema"] == self.SCHEMA

    def test_json_invalido_vira_indisponivel(self, monkeypatch):
        """Resposta quebrada é falha do provedor, não um 500 nosso."""
        self.responder_texto(monkeypatch, "Claro! Aqui está a receita: {nome:")
        with pytest.raises(LLMUnavailableError):
            ask_llm_json("Uma receita", response_schema=self.SCHEMA)
