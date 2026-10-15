"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AppShell, PageHeader } from "@/components/AppShell";
import {
  ClockIcon,
  FlameIcon,
  HeartIcon,
  PlusIcon,
  SearchIcon,
  SparklesIcon,
  UsersIcon,
} from "@/components/icons";
import { PantryMatch, RecipeImage, StarsDisplay } from "@/components/recipe-bits";
import { api, type RecipeScope, type RecipeSummary } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { DIFFICULTY_LABELS, formatMinutes } from "@/lib/format";
import { errorMessage, useResource } from "@/lib/hooks";
import { useToast } from "@/lib/toast";

type Filter = "all" | "cookable" | "favorites" | "mine";

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "Todas" },
  { value: "cookable", label: "Posso fazer agora" },
  { value: "favorites", label: "Favoritas" },
  { value: "mine", label: "Minhas" },
];

export default function RecipesPage() {
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");

  // Espera a pessoa parar de digitar antes de buscar. Sem isso, "strogonoff"
  // dispararia dez requisições, uma por letra.
  useEffect(() => {
    const timer = setTimeout(() => setQuery(search.trim()), 300);
    return () => clearTimeout(timer);
  }, [search]);

  // "Posso fazer agora" não é um filtro do servidor: é a listagem completa
  // filtrada aqui, porque a resposta já traz quantos ingredientes a despensa
  // cobre. Os outros dois viram o parâmetro `scope` da API.
  const scope: RecipeScope = filter === "favorites" || filter === "mine" ? filter : "all";
  const loader = useCallback(
    (token: string) => api.recipes.list(token, { scope, q: query || undefined }),
    [scope, query],
  );
  const { data, error, loading, setData } = useResource(loader);

  const recipes = useMemo(() => {
    if (!data) return [];
    if (filter !== "cookable") return data;
    return data.filter((r) => r.ingredient_count > 0 && r.pantry_have === r.ingredient_count);
  }, [data, filter]);

  return (
    <AppShell>
      <PageHeader
        title="Receitas"
        subtitle="Do caderno da família às sugestões do Chef IA."
        actions={
          <Link href="/recipes/new" className="btn btn-primary">
            <PlusIcon size={18} />
            Nova receita
          </Link>
        }
      />

      <div className="toolbar">
        <div className="search">
          <SearchIcon size={18} />
          <label htmlFor="recipe-search" className="sr-only">
            Buscar receita
          </label>
          <input
            id="recipe-search"
            type="search"
            placeholder="Buscar pelo nome…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            maxLength={100}
          />
        </div>
        <div className="chips" role="group" aria-label="Filtrar receitas">
          {FILTERS.map(({ value, label }) => (
            <button
              key={value}
              type="button"
              className="chip"
              aria-pressed={filter === value}
              onClick={() => setFilter(value)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {loading && !data ? (
        <p className="muted">Carregando receitas…</p>
      ) : recipes.length === 0 ? (
        <EmptyRecipes filter={filter} searching={Boolean(query)} />
      ) : (
        <div className="recipe-grid">
          {recipes.map((recipe) => (
            <RecipeCard
              key={recipe.id}
              recipe={recipe}
              onFavoriteChange={(isFavorite) =>
                setData((current) =>
                  // Em "Favoritas", desfavoritar tira o card da tela.
                  filter === "favorites" && !isFavorite
                    ? (current ?? []).filter((r) => r.id !== recipe.id)
                    : (current ?? []).map((r) =>
                        r.id === recipe.id ? { ...r, is_favorite: isFavorite } : r,
                      ),
                )
              }
            />
          ))}
        </div>
      )}
    </AppShell>
  );
}

function RecipeCard({
  recipe,
  onFavoriteChange,
}: {
  recipe: RecipeSummary;
  onFavoriteChange: (isFavorite: boolean) => void;
}) {
  const { token } = useAuth();
  const toast = useToast();
  const [saving, setSaving] = useState(false);

  async function toggleFavorite() {
    if (!token || saving) return;
    const next = !recipe.is_favorite;
    // Atualização otimista: o coração muda na hora e só volta se a API
    // recusar. Esperar a resposta para pintar um ícone faria o clique parecer
    // não ter funcionado.
    onFavoriteChange(next);
    setSaving(true);
    try {
      await api.recipes.favorite(token, recipe.id, next);
    } catch (caught) {
      onFavoriteChange(!next);
      toast.show(errorMessage(caught), "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <article className="recipe-card">
      <div className="card-badges">
        {recipe.created_by_ai && (
          <span className="badge badge-ai">
            <SparklesIcon size={12} /> IA
          </span>
        )}
      </div>
      <button
        type="button"
        className="fav-button"
        aria-pressed={recipe.is_favorite}
        aria-label={recipe.is_favorite ? "Remover dos favoritos" : "Adicionar aos favoritos"}
        onClick={toggleFavorite}
      >
        <HeartIcon size={20} filled={recipe.is_favorite} />
      </button>

      <Link href={`/recipes/${recipe.id}`} className="recipe-card-link">
        <RecipeImage id={recipe.id} title={recipe.title} imageUrl={recipe.image_url} />
        <div className="recipe-card-body">
          <h3>{recipe.title}</h3>
          <div className="recipe-meta">
            <span>
              <ClockIcon size={14} /> {formatMinutes(recipe.prep_minutes)}
            </span>
            <span>
              <UsersIcon size={14} /> {recipe.servings}
            </span>
            <span>
              <FlameIcon size={14} /> {DIFFICULTY_LABELS[recipe.difficulty]}
            </span>
          </div>
          <StarsDisplay value={recipe.avg_rating} count={recipe.rating_count} />
          <PantryMatch have={recipe.pantry_have} total={recipe.ingredient_count} />
        </div>
      </Link>
    </article>
  );
}

function EmptyRecipes({ filter, searching }: { filter: Filter; searching: boolean }) {
  if (searching) {
    return (
      <div className="empty-state">
        <h2>Nada com esse nome</h2>
        <p>Tente outra palavra — ou peça ao Chef IA uma receita nova.</p>
      </div>
    );
  }
  const messages: Record<Filter, { title: string; text: string }> = {
    all: { title: "Nenhuma receita ainda", text: "Crie a primeira ou peça uma ao Chef IA." },
    cookable: {
      title: "Falta algum ingrediente em todas",
      text: "Cadastre o que tem na despensa, ou mande o que falta para a lista de compras.",
    },
    favorites: { title: "Nenhuma favorita", text: "Toque no coração de uma receita para guardá-la aqui." },
    mine: { title: "Você ainda não criou receitas", text: "Que tal começar pela receita da família?" },
  };
  const { title, text } = messages[filter];
  return (
    <div className="empty-state">
      <h2>{title}</h2>
      <p>{text}</p>
      {filter === "cookable" ? (
        <Link href="/pantry" className="btn btn-secondary">
          Ir para a despensa
        </Link>
      ) : (
        <Link href="/recipes/new" className="btn btn-primary">
          <PlusIcon size={18} /> Nova receita
        </Link>
      )}
    </div>
  );
}
