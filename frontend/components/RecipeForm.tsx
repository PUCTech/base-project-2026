"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";

import {
  ArrowDownIcon,
  ArrowUpIcon,
  ImageIcon,
  PlusIcon,
  SparklesIcon,
  TrashIcon,
} from "@/components/icons";
import { RecipeImage } from "@/components/recipe-bits";
import { ApiError, api, type Difficulty, type RecipeDetail, type RecipeInput } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { takeRecipeDraft } from "@/lib/draft";
import { DIFFICULTY_LABELS } from "@/lib/format";
import { errorMessage } from "@/lib/hooks";
import { useToast } from "@/lib/toast";

// No formulário, número é texto: um campo de quantidade vazio é "", e não 0 —
// e "1,5" precisa ser aceito, porque é assim que se escreve no Brasil.
interface IngredientRow {
  key: number;
  name: string;
  quantity: string;
  unit: string;
  note: string;
}

interface StepRow {
  key: number;
  instruction: string;
  timer: string;
}

let nextKey = 0;
const key = () => ++nextKey;

const emptyIngredient = (): IngredientRow => ({ key: key(), name: "", quantity: "", unit: "", note: "" });
const emptyStep = (): StepRow => ({ key: key(), instruction: "", timer: "" });

function toNumber(text: string): number | null {
  const normalized = text.trim().replace(",", ".");
  if (!normalized) return null;
  const value = Number(normalized);
  return Number.isFinite(value) ? value : NaN;
}

function numberText(value: number | null): string {
  return value === null ? "" : String(value).replace(".", ",");
}

export function RecipeForm({ existing }: { existing?: RecipeDetail }) {
  const { token } = useAuth();
  const router = useRouter();
  const toast = useToast();

  const [title, setTitle] = useState(existing?.title ?? "");
  const [description, setDescription] = useState(existing?.description ?? "");
  const [servings, setServings] = useState(String(existing?.servings ?? 2));
  const [prepMinutes, setPrepMinutes] = useState(numberText(existing?.prep_minutes ?? null));
  const [difficulty, setDifficulty] = useState<Difficulty>(existing?.difficulty ?? "facil");
  const [ingredients, setIngredients] = useState<IngredientRow[]>(
    existing?.ingredients.map((i) => ({
      key: key(),
      name: i.name,
      quantity: numberText(i.quantity),
      unit: i.unit ?? "",
      note: i.note ?? "",
    })) ?? [emptyIngredient(), emptyIngredient(), emptyIngredient()],
  );
  const [steps, setSteps] = useState<StepRow[]>(
    existing?.steps.map((s) => ({
      key: key(),
      instruction: s.instruction,
      timer: numberText(s.timer_minutes),
    })) ?? [emptyStep(), emptyStep()],
  );
  const [createdByAi, setCreatedByAi] = useState(existing?.created_by_ai ?? false);

  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [removeImage, setRemoveImage] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function fill(draft: RecipeInput) {
    setTitle(draft.title);
    setDescription(draft.description);
    setServings(String(draft.servings));
    setPrepMinutes(numberText(draft.prep_minutes));
    setDifficulty(draft.difficulty);
    setIngredients(
      draft.ingredients.map((i) => ({
        key: key(),
        name: i.name,
        quantity: numberText(i.quantity),
        unit: i.unit ?? "",
        note: i.note ?? "",
      })),
    );
    setSteps(
      draft.steps.map((s) => ({ key: key(), instruction: s.instruction, timer: numberText(s.timer_minutes) })),
    );
    setCreatedByAi(true);
  }

  // Rascunho vindo do chat ("Salvar como receita").
  useEffect(() => {
    if (existing) return;
    const draft = takeRecipeDraft();
    if (draft) fill(draft);
  }, [existing]);

  // A prévia da foto é uma URL temporária; ela precisa ser liberada quando
  // trocar ou quando a tela fechar, senão o arquivo fica preso na memória.
  useEffect(() => {
    if (!imageFile) {
      setImagePreview(null);
      return;
    }
    const url = URL.createObjectURL(imageFile);
    setImagePreview(url);
    return () => URL.revokeObjectURL(url);
  }, [imageFile]);

  function buildInput(): RecipeInput | string {
    const filledIngredients = ingredients.filter((i) => i.name.trim());
    const filledSteps = steps.filter((s) => s.instruction.trim());
    if (!filledIngredients.length) return "Inclua ao menos um ingrediente.";
    if (!filledSteps.length) return "Inclua ao menos um passo.";

    const parsed = filledIngredients.map((i) => ({
      name: i.name.trim(),
      quantity: toNumber(i.quantity),
      unit: i.unit.trim() || null,
      note: i.note.trim() || null,
    }));
    const badQuantity = parsed.find((i) => Number.isNaN(i.quantity));
    if (badQuantity) return `A quantidade de "${badQuantity.name}" não é um número.`;

    return {
      title: title.trim(),
      description: description.trim(),
      servings: Number(servings),
      prep_minutes: toNumber(prepMinutes),
      difficulty,
      ingredients: parsed,
      steps: filledSteps.map((s) => ({
        instruction: s.instruction.trim(),
        timer_minutes: toNumber(s.timer),
      })),
      created_by_ai: createdByAi,
    };
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!token || saving) return;

    const input = buildInput();
    if (typeof input === "string") {
      setError(input);
      return;
    }

    setError(null);
    setSaving(true);
    try {
      const saved = existing
        ? await api.recipes.replace(token, existing.id, input)
        : await api.recipes.create(token, input);

      // A foto vai numa segunda chamada, depois que a receita existe. Se ela
      // falhar, a receita continua salva — a pessoa só precisa reenviar a foto.
      try {
        if (imageFile) await api.recipes.uploadImage(token, saved.id, imageFile);
        else if (removeImage && existing?.image_url) await api.recipes.removeImage(token, saved.id);
      } catch (caught) {
        toast.show(`Receita salva, mas a foto não: ${errorMessage(caught)}`, "error");
      }

      toast.show(existing ? "Receita atualizada." : "Receita criada!");
      router.push(`/recipes/${saved.id}`);
    } catch (caught) {
      setError(
        caught instanceof ApiError && caught.status === 422
          ? `Confira os campos: ${caught.message}`
          : errorMessage(caught),
      );
      setSaving(false);
    }
  }

  function move<T>(list: T[], index: number, delta: number): T[] {
    const target = index + delta;
    if (target < 0 || target >= list.length) return list;
    const copy = [...list];
    [copy[index], copy[target]] = [copy[target], copy[index]];
    return copy;
  }

  const currentImage = removeImage ? null : (existing?.image_url ?? null);

  return (
    <>
      {!existing && <AiDraftPanel onDraft={fill} />}

      <form onSubmit={submit} noValidate={false}>
        <section className="panel">
          <div className="panel-title">
            <h2>Sobre a receita</h2>
            {createdByAi && (
              <span className="badge badge-ai">
                <SparklesIcon size={12} /> Rascunho da IA — revise antes de salvar
              </span>
            )}
          </div>

          <div className="field">
            <label htmlFor="title">Nome</label>
            <input
              id="title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              required
              minLength={3}
              maxLength={120}
              placeholder="Bolo de cenoura da vó"
            />
          </div>

          <div className="field">
            <label htmlFor="description">Descrição</label>
            <textarea
              id="description"
              rows={2}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              maxLength={2000}
              placeholder="Uma ou duas frases que dão vontade de fazer."
            />
          </div>

          <div className="field-row">
            <div className="field">
              <label htmlFor="servings">Porções</label>
              <input
                id="servings"
                type="number"
                min={1}
                max={50}
                value={servings}
                onChange={(event) => setServings(event.target.value)}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="prep">Tempo total (min)</label>
              <input
                id="prep"
                type="number"
                min={1}
                max={1440}
                value={prepMinutes}
                onChange={(event) => setPrepMinutes(event.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="difficulty">Dificuldade</label>
              <select
                id="difficulty"
                value={difficulty}
                onChange={(event) => setDifficulty(event.target.value as Difficulty)}
              >
                {Object.entries(DIFFICULTY_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="field" style={{ marginBottom: 0 }}>
            <span className="label">Foto</span>
            <div className="image-picker">
              {imagePreview ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={imagePreview} alt="Prévia da foto" className="recipe-image" />
              ) : existing && currentImage ? (
                <RecipeImage id={existing.id} title={existing.title} imageUrl={currentImage} />
              ) : null}
              <div>
                <label htmlFor="image" className="btn btn-secondary" style={{ marginBottom: 0 }}>
                  <ImageIcon size={17} /> {imagePreview || currentImage ? "Trocar foto" : "Escolher foto"}
                </label>
                <input
                  id="image"
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  className="sr-only"
                  onChange={(event) => {
                    setImageFile(event.target.files?.[0] ?? null);
                    setRemoveImage(false);
                  }}
                />
                {(imagePreview || currentImage) && (
                  <button
                    type="button"
                    className="btn btn-ghost"
                    onClick={() => {
                      setImageFile(null);
                      setRemoveImage(true);
                    }}
                  >
                    Remover
                  </button>
                )}
                <p className="hint">JPEG, PNG ou WebP, até 5 MB.</p>
              </div>
            </div>
          </div>
        </section>

        <section className="panel">
          <div className="panel-title">
            <h2>Ingredientes</h2>
            <span className="muted small">Quantidade vazia = a gosto</span>
          </div>
          <div className="row-editor">
            {ingredients.map((row, index) => (
              <div key={row.key} className="row ingredient-row">
                <input
                  aria-label={`Ingrediente ${index + 1}`}
                  placeholder="Ingrediente"
                  value={row.name}
                  maxLength={100}
                  onChange={(event) =>
                    setIngredients((list) =>
                      list.map((r) => (r.key === row.key ? { ...r, name: event.target.value } : r)),
                    )
                  }
                />
                <input
                  aria-label={`Quantidade de ${row.name || `ingrediente ${index + 1}`}`}
                  placeholder="Qtd."
                  inputMode="decimal"
                  value={row.quantity}
                  onChange={(event) =>
                    setIngredients((list) =>
                      list.map((r) => (r.key === row.key ? { ...r, quantity: event.target.value } : r)),
                    )
                  }
                />
                <input
                  aria-label={`Unidade de ${row.name || `ingrediente ${index + 1}`}`}
                  placeholder="Unidade"
                  value={row.unit}
                  maxLength={20}
                  list="units"
                  onChange={(event) =>
                    setIngredients((list) =>
                      list.map((r) => (r.key === row.key ? { ...r, unit: event.target.value } : r)),
                    )
                  }
                />
                <input
                  aria-label={`Observação de ${row.name || `ingrediente ${index + 1}`}`}
                  placeholder="Observação (picado…)"
                  value={row.note}
                  maxLength={100}
                  onChange={(event) =>
                    setIngredients((list) =>
                      list.map((r) => (r.key === row.key ? { ...r, note: event.target.value } : r)),
                    )
                  }
                />
                <div className="row-actions">
                  <button
                    type="button"
                    className="icon-button"
                    aria-label="Subir ingrediente"
                    disabled={index === 0}
                    onClick={() => setIngredients((list) => move(list, index, -1))}
                  >
                    <ArrowUpIcon size={16} />
                  </button>
                  <button
                    type="button"
                    className="icon-button"
                    aria-label="Descer ingrediente"
                    disabled={index === ingredients.length - 1}
                    onClick={() => setIngredients((list) => move(list, index, 1))}
                  >
                    <ArrowDownIcon size={16} />
                  </button>
                  <button
                    type="button"
                    className="icon-button danger"
                    aria-label="Remover ingrediente"
                    onClick={() => setIngredients((list) => list.filter((r) => r.key !== row.key))}
                  >
                    <TrashIcon size={16} />
                  </button>
                </div>
              </div>
            ))}
          </div>
          <datalist id="units">
            {["g", "kg", "ml", "l", "un", "xícara", "colher de sopa", "colher de chá", "dente", "lata", "caixa", "pitada"].map(
              (unit) => (
                <option key={unit} value={unit} />
              ),
            )}
          </datalist>
          <button
            type="button"
            className="btn btn-ghost"
            style={{ marginTop: 10 }}
            onClick={() => setIngredients((list) => [...list, emptyIngredient()])}
          >
            <PlusIcon size={17} /> Ingrediente
          </button>
        </section>

        <section className="panel">
          <div className="panel-title">
            <h2>Modo de preparo</h2>
            <span className="muted small">O timer aparece no modo cozinha</span>
          </div>
          <div className="row-editor">
            {steps.map((row, index) => (
              <div key={row.key} className="row step-row">
                <span className="row-number" aria-hidden="true">
                  {index + 1}
                </span>
                <textarea
                  aria-label={`Passo ${index + 1}`}
                  rows={2}
                  placeholder="Descreva o passo"
                  value={row.instruction}
                  maxLength={2000}
                  onChange={(event) =>
                    setSteps((list) =>
                      list.map((r) => (r.key === row.key ? { ...r, instruction: event.target.value } : r)),
                    )
                  }
                />
                <input
                  aria-label={`Timer do passo ${index + 1}, em minutos`}
                  placeholder="Timer (min)"
                  type="number"
                  min={1}
                  max={600}
                  value={row.timer}
                  onChange={(event) =>
                    setSteps((list) =>
                      list.map((r) => (r.key === row.key ? { ...r, timer: event.target.value } : r)),
                    )
                  }
                />
                <div className="row-actions">
                  <button
                    type="button"
                    className="icon-button"
                    aria-label="Subir passo"
                    disabled={index === 0}
                    onClick={() => setSteps((list) => move(list, index, -1))}
                  >
                    <ArrowUpIcon size={16} />
                  </button>
                  <button
                    type="button"
                    className="icon-button"
                    aria-label="Descer passo"
                    disabled={index === steps.length - 1}
                    onClick={() => setSteps((list) => move(list, index, 1))}
                  >
                    <ArrowDownIcon size={16} />
                  </button>
                  <button
                    type="button"
                    className="icon-button danger"
                    aria-label="Remover passo"
                    onClick={() => setSteps((list) => list.filter((r) => r.key !== row.key))}
                  >
                    <TrashIcon size={16} />
                  </button>
                </div>
              </div>
            ))}
          </div>
          <button
            type="button"
            className="btn btn-ghost"
            style={{ marginTop: 10 }}
            onClick={() => setSteps((list) => [...list, emptyStep()])}
          >
            <PlusIcon size={17} /> Passo
          </button>
        </section>

        {error && (
          <p className="error" role="alert" style={{ marginTop: 16 }}>
            {error}
          </p>
        )}

        <div className="form-footer">
          <button type="button" className="btn btn-secondary" onClick={() => router.back()}>
            Cancelar
          </button>
          <button type="submit" className="btn btn-primary btn-lg" disabled={saving}>
            {saving ? "Salvando…" : existing ? "Salvar alterações" : "Criar receita"}
          </button>
        </div>
      </form>
    </>
  );
}

const DRAFT_IDEAS = [
  "Um jantar rápido com o que eu tenho",
  "Sobremesa sem forno",
  "Almoço vegetariano para 4 pessoas",
];

function AiDraftPanel({ onDraft }: { onDraft: (draft: RecipeInput) => void }) {
  const { token } = useAuth();
  const [prompt, setPrompt] = useState("");
  const [usePantry, setUsePantry] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function generate(text = prompt) {
    if (!token || text.trim().length < 3) return;
    setPrompt(text);
    setLoading(true);
    setError(null);
    try {
      onDraft(await api.ai.recipeDraft(token, text.trim(), usePantry));
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel ai-panel" style={{ marginBottom: 16 }}>
      <div className="panel-title">
        <h2>
          <SparklesIcon size={20} /> Gerar com IA
        </h2>
      </div>
      <p className="muted small" style={{ marginTop: 0 }}>
        Descreva o que quer comer. O Chef escreve um rascunho, preenche o formulário abaixo e você
        revisa antes de salvar — nada é gravado sem a sua confirmação.
      </p>
      <div className="field">
        <label htmlFor="ai-prompt" className="sr-only">
          O que você quer cozinhar?
        </label>
        <textarea
          id="ai-prompt"
          rows={2}
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          placeholder="Ex.: um jantar leve com frango, pronto em 30 minutos"
          maxLength={2000}
          disabled={loading}
        />
      </div>
      <div className="chips" style={{ marginBottom: 14 }}>
        {DRAFT_IDEAS.map((idea) => (
          <button key={idea} type="button" className="chip" disabled={loading} onClick={() => generate(idea)}>
            {idea}
          </button>
        ))}
      </div>
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <label className="checkbox-label">
          <input type="checkbox" checked={usePantry} onChange={(event) => setUsePantry(event.target.checked)} />
          Usar o que tenho na despensa
        </label>
        <button
          type="button"
          className="btn btn-ai"
          style={{ marginLeft: "auto" }}
          onClick={() => generate()}
          disabled={loading || prompt.trim().length < 3}
        >
          <SparklesIcon size={17} />
          {loading ? "Escrevendo a receita…" : "Gerar rascunho"}
        </button>
      </div>
      {error && (
        <p className="error" role="alert" style={{ margin: "14px 0 0" }}>
          {error}
        </p>
      )}
    </section>
  );
}
