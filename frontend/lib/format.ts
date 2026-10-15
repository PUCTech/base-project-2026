/** Rótulos e formatação para exibir os dados da API em português. */

import type { Category, Difficulty } from "@/lib/api";

export const CATEGORY_LABELS: Record<Category, string> = {
  hortifruti: "Hortifrúti",
  carnes: "Carnes e peixes",
  laticinios: "Laticínios e ovos",
  graos: "Grãos e massas",
  padaria: "Padaria",
  temperos: "Temperos e óleos",
  doces: "Doces",
  bebidas: "Bebidas",
  congelados: "Congelados",
  outros: "Outros",
};

export const DIFFICULTY_LABELS: Record<Difficulty, string> = {
  facil: "Fácil",
  media: "Média",
  dificil: "Difícil",
};

const numberFormat = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });

/** "1,5 kg", "3 un", "a gosto" — a quantidade como uma pessoa escreveria. */
export function formatQuantity(quantity: number | null, unit: string | null): string {
  if (quantity === null) return unit ?? "";
  const number = numberFormat.format(quantity);
  return unit ? `${number} ${unit}` : number;
}

export function formatMinutes(minutes: number | null): string {
  if (!minutes) return "—";
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} h ${rest} min` : `${hours} h`;
}

/** mm:ss (ou h:mm:ss) para o mostrador do timer. */
export function formatClock(totalSeconds: number): string {
  const seconds = Math.max(0, Math.ceil(totalSeconds));
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const mm = String(m).padStart(h ? 2 : 1, "0");
  const ss = String(s).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

/**
 * Dias até a data (negativo se já passou).
 *
 * A data da API é "AAAA-MM-DD", sem fuso. `new Date("2026-10-17")` a leria
 * como meia-noite UTC — que no Brasil ainda é o dia anterior — e o item
 * apareceria vencendo um dia antes. Por isso a data é montada no fuso local.
 */
export function daysUntil(isoDate: string, today = new Date()): number {
  const [year, month, day] = isoDate.split("-").map(Number);
  const target = new Date(year, month - 1, day);
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((target.getTime() - start.getTime()) / 86_400_000);
}

export function formatDate(isoDate: string): string {
  const [year, month, day] = isoDate.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString("pt-BR");
}

const relative = new Intl.RelativeTimeFormat("pt-BR", { numeric: "auto" });

export function timeAgo(isoDateTime: string, now = Date.now()): string {
  const seconds = (new Date(isoDateTime).getTime() - now) / 1000;
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 31_536_000],
    ["month", 2_592_000],
    ["day", 86_400],
    ["hour", 3_600],
    ["minute", 60],
  ];
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) return relative.format(Math.round(seconds / size), unit);
  }
  return "agora";
}

export function plural(count: number, singular: string, pluralForm: string): string {
  return `${count} ${count === 1 ? singular : pluralForm}`;
}
