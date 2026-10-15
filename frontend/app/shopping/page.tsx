"use client";

import { type FormEvent, useMemo, useState } from "react";

import { AppShell, PageHeader } from "@/components/AppShell";
import { CheckIcon, PantryIcon, PlusIcon, SparklesIcon, TrashIcon } from "@/components/icons";
import {
  CATEGORIES,
  api,
  type Category,
  type ShoppingItem,
  type ShoppingSuggestion,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { CATEGORY_LABELS, formatQuantity, plural } from "@/lib/format";
import { errorMessage, useResource } from "@/lib/hooks";
import { useToast } from "@/lib/toast";

const SOURCE_LABELS: Record<ShoppingItem["source"], string | null> = {
  manual: null,
  receita: "da receita",
  ia: "sugestão da IA",
};

export default function ShoppingPage() {
  const { token } = useAuth();
  const toast = useToast();
  const { data: items, error, loading, setData } = useResource(api.shopping.list);
  const [busy, setBusy] = useState(false);

  const pending = useMemo(() => (items ?? []).filter((i) => !i.checked), [items]);
  const inCart = useMemo(() => (items ?? []).filter((i) => i.checked), [items]);
  const groups = CATEGORIES.map((category) => ({
    category,
    items: pending.filter((i) => i.category === category),
  })).filter((g) => g.items.length);

  async function toggle(item: ShoppingItem) {
    if (!token) return;
    const checked = !item.checked;
    // Otimista: no mercado, com sinal fraco, esperar a rede para riscar um
    // item tornaria a lista inutilizável.
    setData((current) => (current ?? []).map((i) => (i.id === item.id ? { ...i, checked } : i)));
    try {
      await api.shopping.update(token, item.id, { checked });
    } catch (caught) {
      setData((current) => (current ?? []).map((i) => (i.id === item.id ? { ...i, checked: !checked } : i)));
      toast.show(errorMessage(caught), "error");
    }
  }

  async function remove(item: ShoppingItem) {
    if (!token) return;
    try {
      await api.shopping.remove(token, item.id);
      setData((current) => (current ?? []).filter((i) => i.id !== item.id));
    } catch (caught) {
      toast.show(errorMessage(caught), "error");
    }
  }

  async function checkout() {
    if (!token) return;
    setBusy(true);
    try {
      const { moved } = await api.shopping.checkout(token);
      setData((current) => (current ?? []).filter((i) => !i.checked));
      toast.show(`${plural(moved, "item foi", "itens foram")} para a despensa. Boa compra!`);
    } catch (caught) {
      toast.show(errorMessage(caught), "error");
    } finally {
      setBusy(false);
    }
  }

  async function clearChecked() {
    if (!token || !window.confirm("Descartar os itens marcados sem levar para a despensa?")) return;
    setBusy(true);
    try {
      await api.shopping.clearChecked(token);
      setData((current) => (current ?? []).filter((i) => !i.checked));
    } catch (caught) {
      toast.show(errorMessage(caught), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        title="Lista de compras"
        subtitle={
          items && items.length
            ? `${plural(pending.length, "item para comprar", "itens para comprar")}${inCart.length ? ` · ${inCart.length} no carrinho` : ""}`
            : "O que falta nas receitas e o que acabou na despensa, num lugar só."
        }
      />

      <SuggestionsPanel onAdded={(list) => setData(list)} />
      <AddForm onAdded={(list) => setData(list)} />

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {loading && !items ? (
        <p className="muted">Carregando lista…</p>
      ) : items?.length === 0 ? (
        <div className="empty-state" style={{ marginTop: 24 }}>
          <h2>Lista vazia</h2>
          <p>
            Abra uma receita e use “Mandar o que falta para a lista”, ou peça sugestões à IA aqui em
            cima.
          </p>
        </div>
      ) : (
        <>
          {groups.map(({ category, items: groupItems }) => (
            <section key={category} className="group">
              <h2 className="group-title">{CATEGORY_LABELS[category]}</h2>
              <ul className="item-list">
                {groupItems.map((item) => (
                  <ShoppingRow key={item.id} item={item} onToggle={() => toggle(item)} onRemove={() => remove(item)} />
                ))}
              </ul>
            </section>
          ))}

          {inCart.length > 0 && (
            <section className="group">
              <h2 className="group-title">
                <CheckIcon size={14} /> No carrinho
              </h2>
              <ul className="item-list">
                {inCart.map((item) => (
                  <ShoppingRow key={item.id} item={item} onToggle={() => toggle(item)} onRemove={() => remove(item)} />
                ))}
              </ul>
            </section>
          )}

          {inCart.length > 0 && (
            <div className="checkout-bar">
              <span>
                <strong>{plural(inCart.length, "item", "itens")}</strong> no carrinho
              </span>
              <div style={{ display: "flex", gap: 8 }}>
                <button type="button" className="btn btn-ghost" onClick={clearChecked} disabled={busy}>
                  Descartar
                </button>
                <button type="button" className="btn btn-primary" onClick={checkout} disabled={busy}>
                  <PantryIcon size={17} /> Finalizar compra
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </AppShell>
  );
}

function ShoppingRow({
  item,
  onToggle,
  onRemove,
}: {
  item: ShoppingItem;
  onToggle: () => void;
  onRemove: () => void;
}) {
  const source = SOURCE_LABELS[item.source];
  return (
    <li className={item.checked ? "item checked" : "item"}>
      <input
        type="checkbox"
        checked={item.checked}
        onChange={onToggle}
        aria-label={item.checked ? `Tirar ${item.name} do carrinho` : `Pôr ${item.name} no carrinho`}
      />
      <div className="item-main">
        <div className="item-name">{item.name}</div>
        {(item.quantity !== null || item.unit || source) && (
          <div className="item-sub">
            {formatQuantity(item.quantity, item.unit) && <span>{formatQuantity(item.quantity, item.unit)}</span>}
            {source && (
              <span className={item.source === "ia" ? "badge badge-ai" : "badge badge-neutral"}>{source}</span>
            )}
          </div>
        )}
      </div>
      <button type="button" className="icon-button danger" aria-label={`Remover ${item.name}`} onClick={onRemove}>
        <TrashIcon size={17} />
      </button>
    </li>
  );
}

function AddForm({ onAdded }: { onAdded: (list: ShoppingItem[]) => void }) {
  const { token } = useAuth();
  const [name, setName] = useState("");
  const [quantity, setQuantity] = useState("");
  const [unit, setUnit] = useState("");
  const [category, setCategory] = useState<Category>("outros");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!token || !name.trim()) return;
    const parsed = quantity.trim() ? Number(quantity.replace(",", ".")) : null;
    if (parsed !== null && !(parsed > 0)) {
      setError("A quantidade precisa ser um número maior que zero.");
      return;
    }
    setError(null);
    try {
      onAdded(await api.shopping.add(token, [{ name: name.trim(), quantity: parsed, unit: unit || null, category }]));
      setName("");
      setQuantity("");
      setUnit("");
    } catch (caught) {
      setError(errorMessage(caught));
    }
  }

  return (
    <section className="panel">
      <form className="add-form add-form-compact" onSubmit={submit}>
        <div className="field">
          <label htmlFor="shop-name">Item</label>
          <input id="shop-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Café" maxLength={100} required />
        </div>
        <div className="field">
          <label htmlFor="shop-qty">Qtd.</label>
          <input id="shop-qty" inputMode="decimal" value={quantity} onChange={(e) => setQuantity(e.target.value)} placeholder="500" />
        </div>
        <div className="field">
          <label htmlFor="shop-unit">Unidade</label>
          <input id="shop-unit" value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="g" maxLength={20} />
        </div>
        <div className="field">
          <label htmlFor="shop-category">Corredor</label>
          <select id="shop-category" value={category} onChange={(e) => setCategory(e.target.value as Category)}>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {CATEGORY_LABELS[c]}
              </option>
            ))}
          </select>
        </div>
        <button type="submit" className="btn btn-primary" disabled={!name.trim()}>
          <PlusIcon size={17} /> Adicionar
        </button>
      </form>
      {error && (
        <p className="error" role="alert" style={{ margin: "12px 0 0" }}>
          {error}
        </p>
      )}
    </section>
  );
}

const GOALS = ["Compras da semana", "Café da manhã", "Churrasco no fim de semana", "Marmitas saudáveis"];

function SuggestionsPanel({ onAdded }: { onAdded: (list: ShoppingItem[]) => void }) {
  const { token } = useAuth();
  const toast = useToast();
  const [goal, setGoal] = useState("");
  const [suggestions, setSuggestions] = useState<ShoppingSuggestion[] | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function suggest(text = goal) {
    if (!token) return;
    setGoal(text);
    setBusy(true);
    setError(null);
    try {
      const result = await api.ai.suggestShopping(token, text.trim() || null);
      setSuggestions(result.suggestions);
      setSelected(new Set(result.suggestions.map((_, i) => i)));
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function addSelected() {
    if (!token || !suggestions) return;
    // O motivo é só para a pessoa decidir; ele não vai para a lista.
    const chosen = suggestions
      .filter((_, i) => selected.has(i))
      .map(({ name, quantity, unit, category }) => ({ name, quantity, unit, category }));
    setBusy(true);
    try {
      onAdded(await api.shopping.add(token, chosen, "ia"));
      toast.show(`${plural(chosen.length, "item foi", "itens foram")} para a lista.`);
      setSuggestions(null);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel ai-panel" style={{ marginBottom: 16 }}>
      <div className="panel-title">
        <h2>
          <SparklesIcon size={20} /> O que comprar?
        </h2>
      </div>

      {suggestions === null ? (
        <>
          <p className="muted small" style={{ marginTop: 0 }}>
            A IA olha sua despensa, o que acabou, o que vence e o que falta nas suas receitas
            favoritas.
          </p>
          <div className="chips" style={{ marginBottom: 12 }}>
            {GOALS.map((g) => (
              <button key={g} type="button" className="chip" onClick={() => suggest(g)} disabled={busy}>
                {g}
              </button>
            ))}
          </div>
          <form
            style={{ display: "flex", gap: 10 }}
            onSubmit={(event) => {
              event.preventDefault();
              void suggest();
            }}
          >
            <label htmlFor="goal" className="sr-only">
              Objetivo da compra
            </label>
            <input
              id="goal"
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="Ou descreva: jantar para 6 pessoas no sábado…"
              maxLength={500}
              disabled={busy}
            />
            <button type="submit" className="btn btn-ai" disabled={busy}>
              <SparklesIcon size={17} /> {busy ? "Pensando…" : "Sugerir"}
            </button>
          </form>
        </>
      ) : suggestions.length === 0 ? (
        <>
          <p className="muted">A IA não viu nada faltando. Despensa em dia!</p>
          <button type="button" className="btn btn-ghost" onClick={() => setSuggestions(null)}>
            Voltar
          </button>
        </>
      ) : (
        <>
          <ul className="review-list">
            {suggestions.map((s, index) => (
              <li key={index}>
                <label className="review-item">
                  <input
                    type="checkbox"
                    checked={selected.has(index)}
                    onChange={() =>
                      setSelected((current) => {
                        const next = new Set(current);
                        if (next.has(index)) next.delete(index);
                        else next.add(index);
                        return next;
                      })
                    }
                  />
                  <span className="item-main">
                    <span className="item-name">
                      {s.name}
                      {(s.quantity || s.unit) && (
                        <span className="muted"> · {formatQuantity(s.quantity ?? null, s.unit ?? null)}</span>
                      )}
                    </span>
                    <span className="item-sub">{s.reason}</span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", flexWrap: "wrap" }}>
            <button type="button" className="btn btn-ghost" onClick={() => setSuggestions(null)} disabled={busy}>
              Descartar
            </button>
            <button type="button" className="btn btn-primary" onClick={addSelected} disabled={busy || !selected.size}>
              <PlusIcon size={17} /> Pôr {plural(selected.size, "item", "itens")} na lista
            </button>
          </div>
        </>
      )}

      {error && (
        <p className="error" role="alert" style={{ margin: "12px 0 0" }}>
          {error}
        </p>
      )}
    </section>
  );
}
