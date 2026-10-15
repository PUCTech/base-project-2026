"""Rotas do chat."""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.routers.llm_errors import llm_errors_as_http
from app.schemas.chat import ChatHistory, ChatRequest, ChatResponse
from app.services.kitchen_ai import chat_reply
from app.services.messages import clear_messages, list_messages, save_exchange

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "",
    response_model=ChatResponse,
    summary="Envia uma pergunta ao LLM",
)
def send_message(
    data: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    """Pergunta ao modelo, grava a troca e devolve a resposta.

    O modelo recebe junto a despensa, a lista de compras e as receitas
    favoritas do usuário, além das últimas falas da conversa — é o que permite
    responder "o que eu faço com o que tenho?". Esse contexto é montado aqui no
    servidor, a cada pergunta, a partir do banco: o navegador não tem como
    enviar uma despensa forjada.

    A chave da API vive no backend, em variável de ambiente. O navegador chama
    esta rota e não tem como alcançar o provedor diretamente — nem como
    descobrir a credencial usada.
    """
    with llm_errors_as_http():
        reply = chat_reply(db, current_user.id, data.message)

    # Só grava depois de ter a resposta em mãos: gravar a pergunta antes da
    # chamada deixaria perguntas órfãs no histórico sempre que o provedor
    # falhasse.
    saved = save_exchange(db, current_user.id, data.message, reply)

    return ChatResponse(reply=reply, created_at=saved.created_at)


@router.get(
    "/history",
    response_model=ChatHistory,
    summary="Histórico de mensagens do usuário",
)
def read_history(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatHistory:
    """Mensagens do usuário autenticado, em ordem cronológica.

    O `user_id` vem do token, nunca da query string: não existe parâmetro que
    permita pedir o histórico de outra conta.
    """
    return ChatHistory(messages=list_messages(db, current_user.id, limit))


@router.delete(
    "/history",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Apaga o histórico e começa uma conversa nova",
)
def delete_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """O histórico entra no contexto de cada pergunta. Começar do zero é o jeito
    de o modelo esquecer um assunto que já não interessa."""
    clear_messages(db, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
