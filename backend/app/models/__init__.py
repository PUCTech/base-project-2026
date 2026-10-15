"""Models do SQLAlchemy.

Importados aqui para que `Base.metadata` conheça todas as tabelas antes de
qualquer `create_all` — e para que os relacionamentos por string ("User",
"Message") consigam ser resolvidos.
"""

from app.models.message import Message
from app.models.pantry_item import PantryItem
from app.models.recipe import Recipe, RecipeIngredient, RecipeStep
from app.models.recipe_social import RecipeComment, RecipeFavorite, RecipeRating
from app.models.user import User

__all__ = [
    "Message",
    "PantryItem",
    "Recipe",
    "RecipeComment",
    "RecipeFavorite",
    "RecipeIngredient",
    "RecipeRating",
    "RecipeStep",
    "User",
]
