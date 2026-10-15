"""Rotas do chat."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.routers.llm_errors import llm_errors_as_http
from app.schemas.chat import ChatHistory, ChatRequest, ChatResponse
from app.services.llm import ask_llm
from app.services.messages import list_messages, save_exchange

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

    A chave da API vive no backend, em variável de ambiente. O navegador chama
    esta rota e não tem como alcançar o provedor diretamente — nem como
    descobrir a credencial usada.
    """
    with llm_errors_as_http():
        reply = ask_llm(data.message)

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
