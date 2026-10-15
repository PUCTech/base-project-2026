"""Dados e atalhos reaproveitados pelos testes de receitas, compras e IA."""

from fastapi.testclient import TestClient

RECEITA = {
    "title": "Omelete de queijo",
    "description": "Rápida e sem erro.",
    "servings": 1,
    "prep_minutes": 10,
    "difficulty": "facil",
    "ingredients": [
        {"name": "Ovos", "quantity": 3, "unit": "un"},
        {"name": "Queijo muçarela", "quantity": 50, "unit": "g", "note": "ralado"},
        {"name": "Sal"},
    ],
    "steps": [
        {"instruction": "Bata os ovos com o sal."},
        {"instruction": "Leve à frigideira e acrescente o queijo.", "timer_minutes": 4},
    ],
}


def criar_receita(client: TestClient, headers: dict, **campos) -> dict:
    response = client.post("/recipes", headers=headers, json={**RECEITA, **campos})
    assert response.status_code == 201, response.text
    return response.json()


def adicionar_na_despensa(client: TestClient, headers: dict, **campos) -> dict:
    response = client.post("/pantry", headers=headers, json=campos)
    assert response.status_code == 201, response.text
    return response.json()
