"""Dados de demonstração: receitas clássicas para a aplicação não começar vazia.

Uso, com o ambiente do docker-compose no ar:

    docker compose exec backend python -m app.seed

As receitas são de uma conta própria, `chef.demo`, e não de quem vai
apresentar: assim dá para favoritar, avaliar e comentar com a sua conta — a
regra de negócio não deixa ninguém avaliar a própria receita.

A senha de `chef.demo` é aleatória e não é exibida: ninguém precisa entrar com
essa conta, e uma senha fixa escrita aqui seria uma credencial versionada.

Rodar de novo não duplica nada: receitas que já existem (mesmo título, mesmo
autor) são puladas.
"""

import secrets

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Recipe, User
from app.schemas.recipe import RecipeCreate
from app.services.recipes import create_recipe
from app.services.security import hash_password

DEMO_USERNAME = "chef.demo"


def _i(name: str, quantity: float | None = None, unit: str | None = None, note: str | None = None):
    return {"name": name, "quantity": quantity, "unit": unit, "note": note}


def _s(instruction: str, timer_minutes: int | None = None):
    return {"instruction": instruction, "timer_minutes": timer_minutes}


RECIPES = [
    {
        "title": "Arroz branco soltinho",
        "description": "O básico que vai com tudo, sem grudar.",
        "servings": 4,
        "prep_minutes": 25,
        "difficulty": "facil",
        "ingredients": [
            _i("Arroz", 2, "xícara"),
            _i("Água", 4, "xícara", "fervente"),
            _i("Cebola", 0.5, "un", "picada"),
            _i("Alho", 2, "dente", "amassado"),
            _i("Óleo", 2, "colher de sopa"),
            _i("Sal", 1, "colher de chá"),
        ],
        "steps": [
            _s("Aqueça o óleo e doure a cebola e o alho.", 2),
            _s("Junte o arroz e refogue, mexendo, até os grãos ficarem esbranquiçados.", 2),
            _s("Acrescente a água fervente e o sal. Tampe parcialmente e cozinhe em fogo baixo.", 15),
            _s("Desligue, tampe totalmente e deixe descansar antes de soltar com um garfo.", 5),
        ],
    },
    {
        "title": "Bolo de cenoura com cobertura de chocolate",
        "description": "Fofinho, de liquidificador, com a cobertura que endurece por cima.",
        "servings": 12,
        "prep_minutes": 60,
        "difficulty": "facil",
        "ingredients": [
            _i("Cenoura", 3, "un", "média, em pedaços"),
            _i("Ovos", 4, "un"),
            _i("Óleo", 1, "xícara"),
            _i("Açúcar", 2, "xícara"),
            _i("Farinha de trigo", 2.5, "xícara"),
            _i("Fermento em pó", 1, "colher de sopa"),
            _i("Chocolate em pó", 4, "colher de sopa", "para a cobertura"),
            _i("Manteiga", 1, "colher de sopa", "para a cobertura"),
            _i("Leite", 5, "colher de sopa", "para a cobertura"),
        ],
        "steps": [
            _s("Preaqueça o forno a 180 °C e unte uma forma com furo no meio.", 10),
            _s("Bata no liquidificador a cenoura, os ovos e o óleo até ficar liso."),
            _s("Numa tigela, misture o creme com o açúcar e a farinha. Por último, o fermento."),
            _s("Despeje na forma e asse até o palito sair limpo.", 40),
            _s("Para a cobertura, leve ao fogo o chocolate, 1 xícara de açúcar, a manteiga e o leite até ferver.", 3),
            _s("Espalhe a cobertura quente sobre o bolo ainda morno."),
        ],
    },
    {
        "title": "Strogonoff de frango",
        "description": "Cremoso, rápido e campeão de pedidos em casa.",
        "servings": 4,
        "prep_minutes": 35,
        "difficulty": "facil",
        "ingredients": [
            _i("Peito de frango", 600, "g", "em cubos"),
            _i("Cebola", 1, "un", "picada"),
            _i("Alho", 2, "dente"),
            _i("Molho de tomate", 3, "colher de sopa"),
            _i("Ketchup", 2, "colher de sopa"),
            _i("Mostarda", 1, "colher de sopa"),
            _i("Creme de leite", 1, "caixa"),
            _i("Champignon", 100, "g", "opcional"),
            _i("Sal"),
        ],
        "steps": [
            _s("Tempere o frango com sal e doure em uma panela com um fio de óleo.", 8),
            _s("Junte a cebola e o alho e refogue até murchar.", 3),
            _s("Acrescente o molho de tomate, o ketchup, a mostarda e o champignon. Cozinhe.", 5),
            _s("Desligue o fogo e misture o creme de leite. Sirva com arroz e batata palha."),
        ],
    },
    {
        "title": "Feijão carioca temperado",
        "description": "Feijão de panela de pressão, com caldo grosso.",
        "servings": 6,
        "prep_minutes": 60,
        "difficulty": "media",
        "ingredients": [
            _i("Feijão carioca", 500, "g", "deixado de molho por 8 h"),
            _i("Água", 1.5, "l"),
            _i("Bacon", 100, "g", "em cubos"),
            _i("Cebola", 1, "un"),
            _i("Alho", 4, "dente"),
            _i("Folha de louro", 2, "un"),
            _i("Sal"),
        ],
        "steps": [
            _s("Escorra o feijão do molho e cozinhe na pressão com a água e o louro.", 30),
            _s("Espere a pressão sair naturalmente antes de abrir a panela.", 10),
            _s("Em outra panela, frite o bacon e doure a cebola e o alho.", 5),
            _s("Junte duas conchas de feijão ao refogado, amasse e devolva tudo à panela.", 10),
        ],
    },
    {
        "title": "Omelete de queijo e tomate",
        "description": "Café da manhã ou jantar em dez minutos.",
        "servings": 1,
        "prep_minutes": 10,
        "difficulty": "facil",
        "ingredients": [
            _i("Ovos", 3, "un"),
            _i("Queijo muçarela", 50, "g", "ralado"),
            _i("Tomate", 1, "un", "sem sementes, em cubos"),
            _i("Manteiga", 1, "colher de chá"),
            _i("Sal"),
            _i("Orégano"),
        ],
        "steps": [
            _s("Bata os ovos com sal até espumar."),
            _s("Derreta a manteiga numa frigideira em fogo médio e despeje os ovos.", 2),
            _s("Quando as bordas firmarem, espalhe o queijo e o tomate de um lado e dobre.", 2),
            _s("Polvilhe orégano e sirva na hora."),
        ],
    },
    {
        "title": "Brigadeiro de panela",
        "description": "Para comer de colher ou enrolar.",
        "servings": 20,
        "prep_minutes": 20,
        "difficulty": "facil",
        "ingredients": [
            _i("Leite condensado", 1, "lata"),
            _i("Chocolate em pó", 3, "colher de sopa"),
            _i("Manteiga", 1, "colher de sopa"),
            _i("Chocolate granulado", None, None, "para enrolar"),
        ],
        "steps": [
            _s("Leve o leite condensado, o chocolate e a manteiga ao fogo baixo, mexendo sem parar.", 12),
            _s("Está no ponto quando desgruda do fundo da panela. Passe para um prato untado."),
            _s("Deixe esfriar antes de enrolar.", 30),
            _s("Com as mãos untadas, enrole e passe no granulado."),
        ],
    },
    {
        "title": "Macarrão alho e óleo",
        "description": "Despensa quase vazia, jantar garantido.",
        "servings": 2,
        "prep_minutes": 15,
        "difficulty": "facil",
        "ingredients": [
            _i("Macarrão espaguete", 250, "g"),
            _i("Alho", 6, "dente", "laminado"),
            _i("Azeite", 4, "colher de sopa"),
            _i("Pimenta calabresa", None, None, "a gosto"),
            _i("Salsinha", None, None, "picada"),
            _i("Sal"),
        ],
        "steps": [
            _s("Cozinhe o macarrão em bastante água fervente com sal, até ficar al dente.", 9),
            _s("Enquanto isso, doure o alho no azeite em fogo baixo, sem queimar.", 3),
            _s("Escorra o macarrão reservando meia xícara da água do cozimento."),
            _s("Misture o macarrão ao alho com a pimenta e um pouco da água reservada. Finalize com salsinha."),
        ],
    },
    {
        "title": "Pão de queijo mineiro",
        "description": "Casquinha crocante e miolo puxa-puxa.",
        "servings": 25,
        "prep_minutes": 50,
        "difficulty": "media",
        "ingredients": [
            _i("Polvilho azedo", 500, "g"),
            _i("Leite", 1, "xícara"),
            _i("Óleo", 0.5, "xícara"),
            _i("Ovos", 2, "un"),
            _i("Queijo meia cura", 200, "g", "ralado"),
            _i("Sal", 1, "colher de chá"),
        ],
        "steps": [
            _s("Ferva o leite com o óleo e o sal e escalde o polvilho, misturando bem.", 5),
            _s("Deixe a massa amornar.", 10),
            _s("Junte os ovos um a um e depois o queijo, sovando até desgrudar das mãos."),
            _s("Preaqueça o forno a 200 °C.", 10),
            _s("Faça bolinhas e asse até dourar.", 25),
        ],
    },
]


def seed() -> None:
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        chef = db.scalar(select(User).where(User.username == DEMO_USERNAME))
        if chef is None:
            chef = User(username=DEMO_USERNAME, password_hash=hash_password(secrets.token_urlsafe(24)))
            db.add(chef)
            db.commit()
            db.refresh(chef)

        existing = set(db.scalars(select(Recipe.title).where(Recipe.author_id == chef.id)))
        created = 0
        for data in RECIPES:
            if data["title"] in existing:
                continue
            # Passa pelo mesmo schema e pelo mesmo serviço da API: o seed não
            # tem um atalho que grave dado que a API recusaria.
            create_recipe(db, chef.id, RecipeCreate.model_validate(data))
            created += 1

    print(f"{created} receita(s) criada(s); {len(RECIPES) - created} já existia(m).")


if __name__ == "__main__":
    seed()
