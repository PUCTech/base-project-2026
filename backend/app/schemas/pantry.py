"""Schemas da despensa."""

from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import Category, ItemName, Unit

# Na despensa, zero é permitido: significa "acabou", e o item fica cadastrado
# para lembrar de comprar.
PantryQuantity = Annotated[float | None, Field(ge=0, le=100_000)]


class PantryItemCreate(BaseModel):
    """Corpo de POST /pantry e de cada item de POST /pantry/batch."""

    name: ItemName
    quantity: PantryQuantity = None
    unit: Unit = None
    category: Category = "outros"
    expires_on: date | None = None


class PantryItemUpdate(BaseModel):
    """Corpo de PATCH /pantry/{id} — atualização parcial.

    `quantity`, `unit` e `expires_on` aceitam `null` explícito, que significa
    "apagar o valor". Por isso o serviço usa `exclude_unset`: ele separa "campo
    não enviado" (não mexe) de "campo enviado como null" (apaga).
    """

    name: ItemName | None = None
    quantity: PantryQuantity = None
    unit: Unit = None
    category: Category | None = None
    expires_on: date | None = None

    @model_validator(mode="after")
    def _require_at_least_one_field(self) -> "PantryItemUpdate":
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualizar.")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("O nome não pode ser apagado.")
        if "category" in self.model_fields_set and self.category is None:
            raise ValueError("A categoria não pode ser apagada.")
        return self


class PantryBatchCreate(BaseModel):
    """Corpo de POST /pantry/batch."""

    items: list[PantryItemCreate] = Field(min_length=1, max_length=100)


class PantryItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    quantity: float | None
    unit: str | None
    category: Category
    expires_on: date | None
    created_at: datetime
    updated_at: datetime
