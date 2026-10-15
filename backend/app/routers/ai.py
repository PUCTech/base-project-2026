"""Rotas das funções de IA da cozinha.

Nenhuma rota aqui grava no banco: todas devolvem uma proposta para a pessoa
revisar na tela. Salvar é feito depois, pelas rotas normais (POST /recipes,
POST /pantry/batch, POST /shopping-list) — com a mesma validação de sempre.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.routers.llm_errors import llm_errors_as_http
from app.schemas.ai import (
    PantryParseRequest,
    PantryParseResponse,
    RecipeDraftRequest,
    ShoppingSuggestRequest,
    ShoppingSuggestResponse,
)
from app.schemas.recipe import RecipeIn
from app.services import kitchen_ai

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post(
    "/recipe-draft",
    response_model=RecipeIn,
    summary="Gera um rascunho de receita para revisar antes de salvar",
)
def recipe_draft(
    data: RecipeDraftRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecipeIn:
    with llm_errors_as_http():
        return kitchen_ai.draft_recipe(db, current_user.id, data.request, data.use_pantry)


@router.post(
    "/pantry-parse",
    response_model=PantryParseResponse,
    summary="Interpreta um texto livre como itens da despensa",
)
def pantry_parse(
    data: PantryParseRequest,
    current_user: User = Depends(get_current_user),
) -> PantryParseResponse:
    # current_user não é usado no corpo, mas a dependência continua aqui: é ela
    # que exige o token. Sem isso, a rota gastaria a cota da IA para qualquer
    # visitante anônimo.
    with llm_errors_as_http():
        return PantryParseResponse(items=kitchen_ai.parse_pantry_text(data.text))


@router.post(
    "/shopping-suggestions",
    response_model=ShoppingSuggestResponse,
    summary="Sugere compras a partir da despensa e das receitas favoritas",
)
def shopping_suggestions(
    data: ShoppingSuggestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShoppingSuggestResponse:
    with llm_errors_as_http():
        suggestions = kitchen_ai.suggest_shopping(db, current_user.id, data.goal)
    return ShoppingSuggestResponse(suggestions=suggestions)
