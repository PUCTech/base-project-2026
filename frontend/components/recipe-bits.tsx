"use client";

/** Peças pequenas reaproveitadas nas telas de receita. */

import { useState } from "react";

import { ChefHatIcon, StarIcon } from "@/components/icons";
import { mediaUrl } from "@/lib/api";

// Paletas quentes para a capa de receitas sem foto. A escolha é derivada do
// id, então a mesma receita tem sempre a mesma cor.
const PLACEHOLDER_TONES = [
  ["#FDE7D3", "#C2410C"],
  ["#E7F0DC", "#3F6B2A"],
  ["#FBE3E1", "#B42318"],
  ["#FEF0C7", "#A15C07"],
  ["#E3ECF5", "#2E5A87"],
  ["#F1E4F3", "#7A3E83"],
];

export function RecipeImage({
  id,
  title,
  imageUrl,
  className = "",
}: {
  id: number;
  title: string;
  imageUrl: string | null;
  className?: string;
}) {
  const src = mediaUrl(imageUrl);
  if (src) {
    return (
      // <img> e não next/image: as fotos já chegam redimensionadas e
      // convertidas para WebP pelo backend, e o otimizador do Next não teria
      // o que acrescentar — só um salto a mais.
      // eslint-disable-next-line @next/next/no-img-element
      <img src={src} alt={title} className={`recipe-image ${className}`} loading="lazy" />
    );
  }
  const [background, foreground] = PLACEHOLDER_TONES[id % PLACEHOLDER_TONES.length];
  return (
    <div
      className={`recipe-image recipe-image-placeholder ${className}`}
      style={{ background, color: foreground }}
      role="img"
      aria-label={`${title} (sem foto)`}
    >
      <ChefHatIcon size={40} />
      <span>{title.charAt(0)}</span>
    </div>
  );
}

/** Estrelas só para leitura: a média de uma receita. */
export function StarsDisplay({
  value,
  count,
  size = 14,
}: {
  value: number | null;
  count?: number;
  size?: number;
}) {
  if (value === null) return <span className="muted stars-empty">Sem avaliações</span>;
  const label = `Nota ${value.toLocaleString("pt-BR")} de 5`;
  return (
    <span className="stars" aria-label={label} title={label}>
      {[1, 2, 3, 4, 5].map((n) => (
        <StarIcon key={n} size={size} filled={n <= Math.round(value)} className="star" />
      ))}
      <span className="stars-value">{value.toLocaleString("pt-BR")}</span>
      {count !== undefined && <span className="muted">({count})</span>}
    </span>
  );
}

/** Estrelas clicáveis para dar nota. Um grupo de rádio, para o teclado funcionar. */
export function StarsInput({
  value,
  onChange,
  disabled,
}: {
  value: number | null;
  onChange: (stars: number) => void;
  disabled?: boolean;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const shown = hover ?? value ?? 0;
  return (
    <div className="stars-input" role="radiogroup" aria-label="Sua nota" onMouseLeave={() => setHover(null)}>
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          role="radio"
          aria-checked={value === n}
          aria-label={`${n} ${n === 1 ? "estrela" : "estrelas"}`}
          className="star-button"
          disabled={disabled}
          onMouseEnter={() => setHover(n)}
          onClick={() => onChange(n)}
        >
          <StarIcon size={26} filled={n <= shown} className="star" />
        </button>
      ))}
    </div>
  );
}

/** Barra "tem X de Y ingredientes". */
export function PantryMatch({ have, total }: { have: number; total: number }) {
  const complete = total > 0 && have === total;
  const percent = total ? Math.round((have / total) * 100) : 0;
  return (
    <div className={complete ? "match match-complete" : "match"}>
      <div className="match-bar" aria-hidden="true">
        <div className="match-fill" style={{ width: `${percent}%` }} />
      </div>
      <span className="match-label">
        {complete ? "Você tem tudo" : `Você tem ${have} de ${total}`}
      </span>
    </div>
  );
}
