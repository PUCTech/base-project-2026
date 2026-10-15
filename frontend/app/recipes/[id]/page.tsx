"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { type FormEvent, useCallback, useState } from "react";

import { AppShell } from "@/components/AppShell";
import {
  AlertIcon,
  CartIcon,
  CheckIcon,
  ChevronLeftIcon,
  ClockIcon,
  EditIcon,
  FlameIcon,
  HeartIcon,
  PlayIcon,
  SparklesIcon,
  TimerIcon,
  TrashIcon,
  UsersIcon,
} from "@/components/icons";
import { PantryMatch, RecipeImage, StarsDisplay, StarsInput } from "@/components/recipe-bits";
import { api, type Comment, type RecipeDetail } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { DIFFICULTY_LABELS, formatMinutes, formatQuantity, plural, timeAgo } from "@/lib/format";
import { errorMessage, useResource } from "@/lib/hooks";
import { useToast } from "@/lib/toast";

export default function RecipePage() {
  const { id } = useParams<{ id: string }>();
  const recipeId = Number(id);

  const loader = useCallback((token: string) => api.recipes.get(token, recipeId), [recipeId]);
  const { data: recipe, error, loading, setData } = useResource(loader);

  return (
    <AppShell>
      <Link href="/recipes" className="back-link">
        <ChevronLeftIcon size={18} /> Receitas
      </Link>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {loading && !recipe && <p className="muted">Carregando receita…</p>}
      {recipe && <RecipeView recipe={recipe} onChange={(next) => setData(next)} />}
    </AppShell>
  );
}

function RecipeView({
  recipe,
  onChange,
}: {
  recipe: RecipeDetail;
  onChange: (recipe: RecipeDetail) => void;
}) {
  const { user, token } = useAuth();
  const router = useRouter();
  const toast = useToast();
  const isAuthor = user?.id === recipe.author.id;

  async function toggleFavorite() {
    if (!token) return;
    const next = !recipe.is_favorite;
    onChange({ ...recipe, is_favorite: next });
    try {
      await api.recipes.favorite(token, recipe.id, next);
    } catch (caught) {
      onChange({ ...recipe, is_favorite: !next });
      toast.show(errorMessage(caught), "error");
    }
  }

  async function remove() {
    if (!token) return;
    // confirm() nativo: simples, acessível e impossível de "pular" sem querer.
    if (!window.confirm(`Apagar "${recipe.title}"? Isso não pode ser desfeito.`)) return;
    try {
      await api.recipes.remove(token, recipe.id);
      toast.show("Receita apagada.");
      router.replace("/recipes");
    } catch (caught) {
      toast.show(errorMessage(caught), "error");
    }
  }

  const missing = recipe.ingredients.filter((i) => !i.in_pantry).length;

  return (
    <>
      <section className="recipe-hero">
        <RecipeImage id={recipe.id} title={recipe.title} imageUrl={recipe.image_url} />

        <div className="recipe-hero-info">
          <div className="chips">
            {recipe.created_by_ai && (
              <span className="badge badge-ai">
                <SparklesIcon size={12} /> Criada com IA
              </span>
            )}
            <span className="badge badge-neutral">por {recipe.author.username}</span>
          </div>

          <h1>{recipe.title}</h1>
          {recipe.description && <p className="recipe-description">{recipe.description}</p>}

          <StarsDisplay value={recipe.avg_rating} count={recipe.rating_count} size={18} />

          <div className="facts">
            <div className="fact">
              <ClockIcon size={18} />
              <strong>{formatMinutes(recipe.prep_minutes)}</strong>
              <span>Tempo</span>
            </div>
            <div className="fact">
              <UsersIcon size={18} />
              <strong>{recipe.servings}</strong>
              <span>Porções</span>
            </div>
            <div className="fact">
              <FlameIcon size={18} />
              <strong>{DIFFICULTY_LABELS[recipe.difficulty]}</strong>
              <span>Dificuldade</span>
            </div>
          </div>

          <PantryMatch have={recipe.pantry_have} total={recipe.ingredient_count} />

          <div className="hero-actions">
            <Link href={`/recipes/${recipe.id}/cook`} className="btn btn-primary btn-lg">
              <PlayIcon size={18} /> Modo cozinha
            </Link>
            <button
              type="button"
              className="btn btn-secondary btn-lg"
              aria-pressed={recipe.is_favorite}
              onClick={toggleFavorite}
            >
              <HeartIcon size={18} filled={recipe.is_favorite} />
              {recipe.is_favorite ? "Favorita" : "Favoritar"}
            </button>
            {isAuthor && (
              <>
                <Link href={`/recipes/${recipe.id}/edit`} className="icon-button" aria-label="Editar receita" title="Editar">
                  <EditIcon size={19} />
                </Link>
                <button type="button" className="icon-button danger" onClick={remove} aria-label="Apagar receita" title="Apagar">
                  <TrashIcon size={19} />
                </button>
              </>
            )}
          </div>
        </div>
      </section>

      <div className="recipe-columns">
        <div>
          <section className="panel">
            <div className="panel-title">
              <h2>Ingredientes</h2>
              {missing > 0 ? (
                <span className="badge badge-warn">faltam {missing}</span>
              ) : (
                <span className="badge badge-herb">tem tudo</span>
              )}
            </div>
            <ul className="ingredient-list">
              {recipe.ingredients.map((ingredient) => (
                <li key={ingredient.id} className="ingredient">
                  <span
                    className={ingredient.in_pantry ? "ingredient-status have" : "ingredient-status missing"}
                    title={ingredient.in_pantry ? "Tem na despensa" : "Falta na despensa"}
                  >
                    {ingredient.in_pantry ? <CheckIcon size={14} /> : <AlertIcon size={13} />}
                  </span>
                  <span>
                    {ingredient.quantity !== null || ingredient.unit ? (
                      <span className="ingredient-qty">
                        {formatQuantity(ingredient.quantity, ingredient.unit)}{" "}
                      </span>
                    ) : null}
                    {ingredient.name}
                    {ingredient.note && <span className="ingredient-note"> — {ingredient.note}</span>}
                    <span className="sr-only">
                      {ingredient.in_pantry ? " (tem na despensa)" : " (falta na despensa)"}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
            <MissingToShopping recipe={recipe} missing={missing} />
          </section>

          <RatingPanel recipe={recipe} isAuthor={isAuthor} onChange={onChange} />
        </div>

        <div>
          <section className="panel">
            <div className="panel-title">
              <h2>Modo de preparo</h2>
              <span className="muted small">{plural(recipe.steps.length, "passo", "passos")}</span>
            </div>
            <ol className="step-list">
              {recipe.steps.map((step) => (
                <li key={step.id} className="step">
                  <div>
                    <p>{step.instruction}</p>
                    {step.timer_minutes && (
                      <span className="timer-chip">
                        <TimerIcon size={13} /> {formatMinutes(step.timer_minutes)}
                      </span>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </section>

          <Comments recipe={recipe} isRecipeAuthor={isAuthor} />
        </div>
      </div>
    </>
  );
}

function MissingToShopping({ recipe, missing }: { recipe: RecipeDetail; missing: number }) {
  const { token } = useAuth();
  const toast = useToast();
  const [servings, setServings] = useState(recipe.servings);
  const [sending, setSending] = useState(false);

  async function send() {
    if (!token) return;
    setSending(true);
    try {
      const { added } = await api.shopping.fromRecipe(
        token,
        recipe.id,
        servings === recipe.servings ? undefined : servings,
      );
      toast.show(
        added
          ? `${plural(added, "item foi", "itens foram")} para a lista de compras.`
          : "Você já tem tudo para essa quantidade.",
        added ? "success" : "info",
      );
    } catch (caught) {
      toast.show(errorMessage(caught), "error");
    } finally {
      setSending(false);
    }
  }

  // Mesmo com tudo na despensa, mudar as porções pode criar falta — por isso
  // o seletor aparece sempre, e o botão só some quando não há nada a fazer.
  return (
    <div className="missing-actions">
      <label htmlFor="servings" className="sr-only">
        Porções
      </label>
      <select
        id="servings"
        value={servings}
        onChange={(event) => setServings(Number(event.target.value))}
      >
        {Array.from(new Set([1, 2, 4, 6, 8, 10, 12, recipe.servings]))
          .sort((a, b) => a - b)
          .map((n) => (
            <option key={n} value={n}>
              {plural(n, "porção", "porções")}
            </option>
          ))}
      </select>
      <button
        type="button"
        className="btn btn-secondary"
        onClick={send}
        disabled={sending || (missing === 0 && servings <= recipe.servings)}
      >
        <CartIcon size={17} />
        {sending ? "Enviando…" : "Mandar o que falta para a lista"}
      </button>
    </div>
  );
}

function RatingPanel({
  recipe,
  isAuthor,
  onChange,
}: {
  recipe: RecipeDetail;
  isAuthor: boolean;
  onChange: (recipe: RecipeDetail) => void;
}) {
  const { token } = useAuth();
  const toast = useToast();
  const [saving, setSaving] = useState(false);

  async function rate(stars: number | null) {
    if (!token) return;
    setSaving(true);
    try {
      const summary =
        stars === null
          ? await api.recipes.unrate(token, recipe.id)
          : await api.recipes.rate(token, recipe.id, stars);
      onChange({ ...recipe, ...summary });
    } catch (caught) {
      toast.show(errorMessage(caught), "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel-title">
        <h2>Avaliação</h2>
        <StarsDisplay value={recipe.avg_rating} count={recipe.rating_count} />
      </div>
      {isAuthor ? (
        <p className="muted small" style={{ margin: 0 }}>
          A receita é sua — as notas vêm de quem cozinhar.
        </p>
      ) : (
        <div className="rating-box">
          <StarsInput value={recipe.my_rating} onChange={rate} disabled={saving} />
          {recipe.my_rating !== null && (
            <button type="button" className="btn btn-ghost" onClick={() => rate(null)} disabled={saving}>
              Remover nota
            </button>
          )}
        </div>
      )}
    </section>
  );
}

function Comments({ recipe, isRecipeAuthor }: { recipe: RecipeDetail; isRecipeAuthor: boolean }) {
  const { user, token } = useAuth();
  const toast = useToast();
  const loader = useCallback((t: string) => api.recipes.comments(t, recipe.id), [recipe.id]);
  const { data: comments, setData } = useResource<Comment[]>(loader);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const content = draft.trim();
    if (!token || !content) return;
    setSending(true);
    try {
      const created = await api.recipes.comment(token, recipe.id, content);
      setData((current) => [...(current ?? []), created]);
      setDraft("");
    } catch (caught) {
      toast.show(errorMessage(caught), "error");
    } finally {
      setSending(false);
    }
  }

  async function remove(comment: Comment) {
    if (!token || !window.confirm("Apagar este comentário?")) return;
    try {
      await api.recipes.removeComment(token, recipe.id, comment.id);
      setData((current) => (current ?? []).filter((c) => c.id !== comment.id));
    } catch (caught) {
      toast.show(errorMessage(caught), "error");
    }
  }

  return (
    <section className="panel">
      <div className="panel-title">
        <h2>Comentários</h2>
        {comments && <span className="muted small">{comments.length}</span>}
      </div>

      {comments?.length === 0 && (
        <p className="muted small" style={{ marginTop: 0 }}>
          Ninguém comentou ainda. Fez a receita? Conte como ficou.
        </p>
      )}

      {comments?.map((comment) => (
        <div key={comment.id} className="comment">
          <span className="avatar" aria-hidden="true">
            {comment.author.username.charAt(0)}
          </span>
          <div className="comment-body">
            <div className="comment-head">
              <strong>{comment.author.username}</strong>
              <span className="muted">{timeAgo(comment.created_at)}</span>
            </div>
            {/* Texto de outra pessoa entra como texto, não como HTML: o React
                escapa o conteúdo, então um comentário com <script> não executa. */}
            <p>{comment.content}</p>
          </div>
          {(comment.author.id === user?.id || isRecipeAuthor) && (
            <button
              type="button"
              className="icon-button danger"
              aria-label="Apagar comentário"
              onClick={() => remove(comment)}
            >
              <TrashIcon size={16} />
            </button>
          )}
        </div>
      ))}

      <form className="comment-form" onSubmit={submit}>
        <div style={{ flex: 1 }}>
          <label htmlFor="comment" className="sr-only">
            Seu comentário
          </label>
          <textarea
            id="comment"
            rows={2}
            placeholder="Fiz e ficou ótimo! Troquei…"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            maxLength={1000}
            disabled={sending}
          />
        </div>
        <button type="submit" className="btn btn-primary" disabled={sending || !draft.trim()}>
          Comentar
        </button>
      </form>
    </section>
  );
}
