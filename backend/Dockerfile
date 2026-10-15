# syntax=docker/dockerfile:1

# ============================================================================
# Estágio 1 — builder: compila as dependências em wheels
# ============================================================================
# Separar a construção da execução mantém fora da imagem final o compilador e
# os headers necessários para instalar os pacotes. O que não está na imagem não
# precisa ser corrigido quando aparece uma CVE.
FROM python:3.12-slim AS builder

WORKDIR /build

# Copiar só o requirements antes do código é o que faz o cache do Docker
# funcionar: enquanto as dependências não mudarem, esta camada é reaproveitada
# e nenhum `pip install` roda de novo a cada alteração no código.
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# ============================================================================
# Estágio 2 — runtime
# ============================================================================
FROM python:3.12-slim AS runtime

# PYTHONUNBUFFERED: sem isso, o stdout fica em buffer e os logs só aparecem
# quando o buffer enche — tornando inútil o `docker logs -f` em um container
# que travou.
# PYTHONDONTWRITEBYTECODE: .pyc não serve num sistema de arquivos efêmero.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Usuário sem privilégios. O padrão do Docker é rodar como root, e um processo
# exposto à internet rodando como root transforma qualquer execução remota de
# código em controle total do container.
RUN useradd --create-home --uid 1000 appuser

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/* \
    && rm -rf /wheels

COPY --chown=appuser:appuser app ./app

# Diretório das fotos enviadas, de propriedade do usuário sem privilégios. O
# volume do compose é montado aqui, e um volume nomeado novo herda o dono deste
# diretório — sem isso, o appuser não teria permissão de gravar nele.
RUN mkdir -p /app/media && chown appuser:appuser /app/media

USER appuser

EXPOSE 8000

# Sem --reload: recarregar em produção gasta memória vigiando o sistema de
# arquivos e reinicia o processo a cada arquivo alterado.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
