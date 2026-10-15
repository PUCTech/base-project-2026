"use client";

import { type FormEvent, useMemo, useState } from "react";

import { AppShell, PageHeader } from "@/components/AppShell";
import {
  CartIcon,
  CheckIcon,
  EditIcon,
  MinusIcon,
  PlusIcon,
  SearchIcon,
  SparklesIcon,
  TrashIcon,
  XIcon,
} from "@/components/icons";
import {
  ApiError,
  CATEGORIES,
  api,
  type Category,
  type PantryItem,
  type PantryItemInput,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { CATEGORY_LABELS, daysUntil, formatDate, formatQuantity, plural } from "@/lib/format";
import { errorMessage, useResource } from "@/lib/hooks";
import { useToast } from "@/lib/toast";

/** Itens que vencem em até este número de dias ganham destaque. */
const EXPIRING_DAYS = 5;

export default function PantryPage() {
  const { data: items, error, loading, setData, reload } = useResource(api.pantry.list);
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (items ?? []).filter((item) => !term || item.name.toLowerCase().includes(term));
  }, [items, search]);

  const groups = useMemo(
    () =>
      CATEGORIES.map((category) => ({
        category,
        items: filtered.filter((item) => item.category === category),
      })).filter((group) => group.items.length),
    [filtered],
  );

  const expiring = (items ?? []).filter(
    (item) => item.expires_on !== null && daysUntil(item.expires_on) <= EXPIRING_DAYS,
  ).length;
  const finished = (items ?? []).filter((item) => item.quantity === 0).length;

  function replaceItem(updated: PantryItem) {
    setData((current) => (current ?? []).map((item) => (item.id === updated.id ? updated : item)));
  }

  return (
    <AppShell>
      <PageHeader title="Despensa" subtitle="O que você tem em casa — a base de tudo que o Chef sugere." />

      {items && items.length > 0 && (
        <div className="stats">
          <div className="stat">
            <strong>{items.length}</strong>
            <span>itens na despensa</span>
          </div>
          <div className={expiring ? "stat warn" : "stat"}>
            <strong>{expiring}</strong>
            <span>vencem em até {EXPIRING_DAYS} dias</span>
          </div>
          <div className="stat">
            <strong>{finished}</strong>
            <span>{finished === 1 ? "acabou" : "acabaram"}</span>
          </div>
        </div>
      )}

      <QuickAddPanel onAdded={reload} />
      <AddItemForm onAdded={(item) => setData((current) => [...(current ?? []), item])} />

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {items && items.length > 0 && (
        <div className="search" style={{ marginTop: 24, maxWidth: 360 }}>
          <SearchIcon size={18} />
          <label htmlFor="pantry-search" className="sr-only">
            Filtrar despensa
          </label>
          <input
            id="pantry-search"
            type="search"
            placeholder="Filtrar itens…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
      )}

      {loading && !items ? (
        <p className="muted">Carregando despensa…</p>
      ) : items?.length === 0 ? (
        <div className="empty-state" style={{ marginTop: 24 }}>
          <h2>Despensa vazia</h2>
          <p>
            Comece pelo cadastro rápido: escreva o que comprou do jeito que falaria, e a IA organiza
            para você revisar.
          </p>
        </div>
      ) : (
        groups.map(({ category, items: groupItems }) => (
          <section key={category} className="group">
            <h2 className="group-title">
              {CATEGORY_LABELS[category]} <span>· {groupItems.length}</span>
            </h2>
            <ul className="item-list">
              {groupItems.map((item) => (
                <PantryRow
                  key={item.id}
                  item={item}
                  onChange={replaceItem}
                  onRemove={() => setData((current) => (current ?? []).filter((i) => i.id !== item.id))}
                />
              ))}
            </ul>
          </section>
        ))
      )}
    </AppShell>
  );
}

function ExpiryBadge({ date }: { date: string }) {
  const days = daysUntil(date);
  if (days < 0) return <span className="badge badge-danger">vencido</span>;
  if (days === 0) return <span className="badge badge-danger">vence hoje</span>;
  if (days <= EXPIRING_DAYS) return <span className="badge badge-warn">vence em {plural(days, "dia", "dias")}</span>;
  return <span>validade {formatDate(date)}</span>;
}

/** Quanto o + e o − mudam, conforme a unidade. */
function stepFor(unit: string | null): number {
  const normalized = (unit ?? "").toLowerCase();
  if (normalized === "g" || normalized === "ml") return 100;
  if (normalized === "kg" || normalized === "l") return 0.5;
  return 1;
}

function PantryRow({
  item,
  onChange,
  onRemove,
}: {
  item: PantryItem;
  onChange: (item: PantryItem) => void;
  onRemove: () => void;
}) {
  const { token } = useAuth();
  const toast = useToast();
  const [editing, setEditing] = useState(false);

  async function update(changes: Partial<PantryItemInput>) {
    if (!token) return;
    try {
      onChange(await api.pantry.update(token, item.id, changes));
    } catch (caught) {
      toast.show(errorMessage(caught), "error");
    }
  }

  async function adjust(delta: number) {
    if (item.quantity === null) return;
    const next = Math.max(0, Math.round((item.quantity + delta) * 1000) / 1000);
    await update({ quantity: next });
  }

  async function remove() {
    if (!token || !window.confirm(`Tirar "${item.name}" da despensa?`)) return;
    try {
      await api.pantry.remove(token, item.id);
      onRemove();
    } catch (caught) {
      toast.show(errorMessage(caught), "error");
    }
  }

  async function sendToShopping() {
    if (!token) return;
    try {
      await api.shopping.add(token, [{ name: item.name, unit: item.unit, category: item.category }]);
      toast.show(`${item.name} foi para a lista de compras.`);
    } catch (caught) {
      toast.show(errorMessage(caught), "error");
    }
  }

  if (editing) {
    return (
      <li className="item">
        <EditItemForm
          item={item}
          onCancel={() => setEditing(false)}
          onSave={async (changes) => {
            await update(changes);
            setEditing(false);
          }}
        />
      </li>
    );
  }

  const step = stepFor(item.unit);

  return (
    <li className="item">
      <div className="item-main">
        <div className="item-name">{item.name}</div>
        <div className="item-sub">
          {item.quantity === 0 ? (
            <span className="badge badge-danger">acabou</span>
          ) : item.quantity === null ? (
            <span>quantidade não controlada</span>
          ) : null}
          {item.expires_on && <ExpiryBadge date={item.expires_on} />}
        </div>
      </div>

      {item.quantity !== null && (
        <div className="qty-stepper">
          <button
            type="button"
            className="icon-button"
            aria-label={`Diminuir ${item.name}`}
            disabled={item.quantity === 0}
            onClick={() => adjust(-step)}
          >
            <MinusIcon size={16} />
          </button>
          <span className="qty-value">{formatQuantity(item.quantity, item.unit)}</span>
          <button
            type="button"
            className="icon-button"
            aria-label={`Aumentar ${item.name}`}
            onClick={() => adjust(step)}
          >
            <PlusIcon size={16} />
          </button>
        </div>
      )}

      {item.quantity === 0 && (
        <button
          type="button"
          className="icon-button"
          aria-label={`Pôr ${item.name} na lista de compras`}
          title="Pôr na lista de compras"
          onClick={sendToShopping}
        >
          <CartIcon size={17} />
        </button>
      )}
      <button type="button" className="icon-button" aria-label={`Editar ${item.name}`} onClick={() => setEditing(true)}>
        <EditIcon size={17} />
      </button>
      <button type="button" className="icon-button danger" aria-label={`Remover ${item.name}`} onClick={remove}>
        <TrashIcon size={17} />
      </button>
    </li>
  );
}

function parseQuantity(text: string): number | null {
  const normalized = text.trim().replace(",", ".");
  return normalized ? Number(normalized) : null;
}

function EditItemForm({
  item,
  onSave,
  onCancel,
}: {
  item: PantryItem;
  onSave: (changes: Partial<PantryItemInput>) => Promise<void>;
  onCancel: () => void;
}) {
  const [name, setName] = useState(item.name);
  const [quantity, setQuantity] = useState(item.quantity === null ? "" : String(item.quantity).replace(".", ","));
  const [unit, setUnit] = useState(item.unit ?? "");
  const [category, setCategory] = useState<Category>(item.category);
  const [expiresOn, setExpiresOn] = useState(item.expires_on ?? "");

  return (
    <form
      className="item-edit"
      onSubmit={(event) => {
        event.preventDefault();
        void onSave({
          name,
          quantity: parseQuantity(quantity),
          unit: unit || null,
          category,
          expires_on: expiresOn || null,
        });
      }}
    >
      <input aria-label="Nome" value={name} onChange={(e) => setName(e.target.value)} required maxLength={100} />
      <input aria-label="Quantidade" inputMode="decimal" placeholder="Qtd." value={quantity} onChange={(e) => setQuantity(e.target.value)} />
      <input aria-label="Unidade" placeholder="Unid." value={unit} onChange={(e) => setUnit(e.target.value)} maxLength={20} />
      <select aria-label="Categoria" value={category} onChange={(e) => setCategory(e.target.value as Category)}>
        {CATEGORIES.map((c) => (
          <option key={c} value={c}>
            {CATEGORY_LABELS[c]}
          </option>
        ))}
      </select>
      <input aria-label="Validade" type="date" value={expiresOn} onChange={(e) => setExpiresOn(e.target.value)} />
      <div className="row-actions">
        <button type="submit" className="icon-button" aria-label="Salvar">
          <CheckIcon size={18} />
        </button>
        <button type="button" className="icon-button" aria-label="Cancelar" onClick={onCancel}>
          <XIcon size={18} />
        </button>
      </div>
    </form>
  );
}

function AddItemForm({ onAdded }: { onAdded: (item: PantryItem) => void }) {
  const { token } = useAuth();
  const [name, setName] = useState("");
  const [quantity, setQuantity] = useState("");
  const [unit, setUnit] = useState("");
  const [category, setCategory] = useState<Category>("outros");
  const [expiresOn, setExpiresOn] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!token || !name.trim()) return;
    const parsed = parseQuantity(quantity);
    if (parsed !== null && Number.isNaN(parsed)) {
      setError("A quantidade precisa ser um número.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      onAdded(
        await api.pantry.add(token, {
          name: name.trim(),
          quantity: parsed,
          unit: unit || null,
          category,
          expires_on: expiresOn || null,
        }),
      );
      setName("");
      setQuantity("");
      setUnit("");
      setExpiresOn("");
    } catch (caught) {
      setError(
        caught instanceof ApiError && caught.status === 409
          ? `"${name.trim()}" já está na despensa. Ajuste a quantidade dele na lista abaixo.`
          : errorMessage(caught),
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel-title">
        <h2>Adicionar item</h2>
      </div>
      <form className="add-form" onSubmit={submit}>
        <div className="field">
          <label htmlFor="pantry-name">Item</label>
          <input id="pantry-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Arroz" required maxLength={100} />
        </div>
        <div className="field">
          <label htmlFor="pantry-qty">Qtd.</label>
          <input id="pantry-qty" inputMode="decimal" value={quantity} onChange={(e) => setQuantity(e.target.value)} placeholder="2" />
        </div>
        <div className="field">
          <label htmlFor="pantry-unit">Unidade</label>
          <input id="pantry-unit" value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="kg" maxLength={20} list="pantry-units" />
          <datalist id="pantry-units">
            {["g", "kg", "ml", "l", "un", "pacote", "lata", "caixa", "dúzia"].map((u) => (
              <option key={u} value={u} />
            ))}
          </datalist>
        </div>
        <div className="field">
          <label htmlFor="pantry-category">Categoria</label>
          <select id="pantry-category" value={category} onChange={(e) => setCategory(e.target.value as Category)}>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {CATEGORY_LABELS[c]}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="pantry-expires">Validade</label>
          <input id="pantry-expires" type="date" value={expiresOn} onChange={(e) => setExpiresOn(e.target.value)} />
        </div>
        <button type="submit" className="btn btn-primary" disabled={saving || !name.trim()}>
          <PlusIcon size={17} /> Adicionar
        </button>
      </form>
      <p className="hint">Quantidade vazia = &quot;tenho, sem controlar quanto&quot; (sal, azeite…). Zero = acabou.</p>
      {error && (
        <p className="error" role="alert" style={{ margin: "12px 0 0" }}>
          {error}
        </p>
      )}
    </section>
  );
}

/**
 * Cadastro rápido: texto livre → IA interpreta → pessoa revisa → lote.
 *
 * A IA só propõe. Os itens aparecem marcados para revisão, e só os que
 * continuarem marcados vão para a API — pela rota normal de cadastro em lote,
 * com a mesma validação de sempre.
 */
function QuickAddPanel({ onAdded }: { onAdded: () => void }) {
  const { token } = useAuth();
  const toast = useToast();
  const [text, setText] = useState("");
  const [parsed, setParsed] = useState<PantryItemInput[] | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function interpret() {
    if (!token || text.trim().length < 3) return;
    setBusy(true);
    setError(null);
    try {
      const { items } = await api.ai.parsePantry(token, text.trim());
      setParsed(items);
      setSelected(new Set(items.map((_, index) => index)));
      if (!items.length) setError("Não encontrei itens de cozinha nesse texto.");
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    if (!token || !parsed) return;
    const chosen = parsed.filter((_, index) => selected.has(index));
    if (!chosen.length) return;
    setBusy(true);
    try {
      await api.pantry.addMany(token, chosen);
      toast.show(`${plural(chosen.length, "item foi", "itens foram")} para a despensa.`);
      setParsed(null);
      setText("");
      onAdded();
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
          <SparklesIcon size={20} /> Cadastro rápido com IA
        </h2>
      </div>

      {parsed === null || parsed.length === 0 ? (
        <>
          <p className="muted small" style={{ marginTop: 0 }}>
            Escreva o que comprou como falaria. Você confere tudo antes de entrar na despensa.
          </p>
          <label htmlFor="quick-add" className="sr-only">
            O que você comprou?
          </label>
          <textarea
            id="quick-add"
            rows={2}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Comprei 2 kg de arroz, uma dúzia de ovos, meio quilo de tomate e um litro de leite"
            maxLength={2000}
            disabled={busy}
          />
          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 10 }}>
            <button type="button" className="btn btn-ai" onClick={interpret} disabled={busy || text.trim().length < 3}>
              <SparklesIcon size={17} /> {busy ? "Interpretando…" : "Interpretar"}
            </button>
          </div>
        </>
      ) : (
        <>
          <p className="muted small" style={{ marginTop: 0 }}>
            Confira o que a IA entendeu. Desmarque o que não quiser adicionar.
          </p>
          <ul className="review-list">
            {parsed.map((item, index) => (
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
                    <span className="item-name">{item.name}</span>
                    <span className="item-sub">
                      {formatQuantity(item.quantity ?? null, item.unit ?? null) || "sem quantidade"} ·{" "}
                      {CATEGORY_LABELS[item.category ?? "outros"]}
                    </span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", flexWrap: "wrap" }}>
            <button type="button" className="btn btn-ghost" onClick={() => setParsed(null)} disabled={busy}>
              Voltar ao texto
            </button>
            <button type="button" className="btn btn-primary" onClick={confirm} disabled={busy || selected.size === 0}>
              <CheckIcon size={17} /> Adicionar {plural(selected.size, "item", "itens")}
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
