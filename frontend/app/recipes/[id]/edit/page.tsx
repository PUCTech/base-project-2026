"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback } from "react";

import { AppShell, PageHeader } from "@/components/AppShell";
import { ChevronLeftIcon } from "@/components/icons";
import { RecipeForm } from "@/components/RecipeForm";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/hooks";

export default function EditRecipePage() {
  const { id } = useParams<{ id: string }>();
  const recipeId = Number(id);
  const { user } = useAuth();
  const loader = useCallback((token: string) => api.recipes.get(token, recipeId), [recipeId]);
  const { data: recipe, error } = useResource(loader);

  return (
    <AppShell>
      <Link href={`/recipes/${recipeId}`} className="back-link">
        <ChevronLeftIcon size={18} /> Voltar para a receita
      </Link>
      <PageHeader title="Editar receita" />
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {/* Só o autor vê o formulário. A regra de verdade está na API, que
          responde 403 para qualquer outro — aqui é só para não oferecer um
          formulário que falharia ao salvar. */}
      {recipe && user && recipe.author.id !== user.id ? (
        <p className="error" role="alert">
          Só quem criou a receita pode editá-la.
        </p>
      ) : (
        recipe && <RecipeForm existing={recipe} />
      )}
    </AppShell>
  );
}
