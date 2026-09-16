"""Models do SQLAlchemy.

Importados aqui para que `Base.metadata` conheça todas as tabelas antes de
qualquer `create_all` — e para que os relacionamentos por string ("User",
"Message") consigam ser resolvidos.
"""

from app.models.message import Message
from app.models.user import User

__all__ = ["Message", "User"]
