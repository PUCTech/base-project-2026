"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import {
  CheckIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  PauseIcon,
  PlayIcon,
  ResetIcon,
  TimerIcon,
  XIcon,
} from "@/components/icons";
import { api, type RecipeDetail } from "@/lib/api";
import { formatClock, formatQuantity } from "@/lib/format";
import { useResource } from "@/lib/hooks";
import { type KitchenTimer, remaining, useKitchenTimers, useWakeLock } from "@/lib/timers";

export default function CookPage() {
  const { id } = useParams<{ id: string }>();
  const recipeId = Number(id);
  const loader = useCallback((token: string) => api.recipes.get(token, recipeId), [recipeId]);
  const { data: recipe, error } = useResource(loader);

  return (
    <AppShell wide>
      {error && (
        <div className="page">
          <p className="error" role="alert">
            {error}
          </p>
        </div>
      )}
      {recipe ? (
        <CookMode recipe={recipe} />
      ) : (
        !error && (
          <div className="page">
            <p className="muted">Preparando a cozinha…</p>
          </div>
        )
      )}
    </AppShell>
  );
}

function CookMode({ recipe }: { recipe: RecipeDetail }) {
  const [index, setIndex] = useState(0);
  const [prepared, setPrepared] = useState<Set<number>>(new Set());
  const { timers, now, start, toggle, reset, dismiss } = useKitchenTimers();
  const screenAwake = useWakeLock();

  const step = recipe.steps[index];
  const isLast = index === recipe.steps.length - 1;
  const stepLabel = (i: number) => `Passo ${i + 1}`;
  // O timer deste passo, se já tiver sido iniciado. Mudar de passo não para o
  // timer: o arroz continua cozinhando enquanto a pessoa pica a cebola.
  const stepTimer = timers.find((t) => t.label === stepLabel(index));

  // Setas do teclado para navegar — útil com o notebook na bancada.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
      if (event.key === "ArrowRight") setIndex((i) => Math.min(i + 1, recipe.steps.length - 1));
      if (event.key === "ArrowLeft") setIndex((i) => Math.max(i - 1, 0));
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [recipe.steps.length]);

  const progress = ((index + 1) / recipe.steps.length) * 100;

  return (
    <div className="cook">
      <div className="cook-head">
        <Link href={`/recipes/${recipe.id}`} className="back-link" style={{ margin: 0 }}>
          <XIcon size={18} /> Sair
        </Link>
        <h1>{recipe.title}</h1>
        <span className="muted small cook-awake" title="A tela não apaga enquanto o modo cozinha estiver aberto">
          {screenAwake ? "Tela sempre acesa" : ""}
        </span>
      </div>
      <div className="cook-progress" aria-hidden="true">
        <div style={{ width: `${progress}%` }} />
      </div>

      <div className="cook-body">
        <section className="cook-step" aria-live="polite">
          <span className="cook-step-label">
            Passo {index + 1} de {recipe.steps.length}
          </span>
          <p className="cook-step-text">{step.instruction}</p>

          {step.timer_minutes && (
            <div className="cook-timer">
              <TimerIcon size={26} />
              <span className="cook-timer-clock">
                {formatClock((stepTimer ? remaining(stepTimer, now) : step.timer_minutes * 60_000) / 1000)}
              </span>
              {stepTimer ? (
                <>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => toggle(stepTimer.id)}
                    disabled={stepTimer.done}
                  >
                    {stepTimer.endsAt === null ? <PlayIcon size={16} /> : <PauseIcon size={16} />}
                    {stepTimer.endsAt === null ? "Continuar" : "Pausar"}
                  </button>
                  <button type="button" className="btn btn-secondary" onClick={() => reset(stepTimer.id)}>
                    <ResetIcon size={16} /> Zerar
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  className="btn btn-primary btn-lg"
                  onClick={() => start(stepLabel(index), step.timer_minutes!)}
                >
                  <PlayIcon size={18} /> Iniciar timer
                </button>
              )}
            </div>
          )}

          <div className="cook-nav">
            <button
              type="button"
              className="btn btn-secondary btn-lg"
              onClick={() => setIndex((i) => i - 1)}
              disabled={index === 0}
            >
              <ChevronLeftIcon size={18} /> Anterior
            </button>
            {isLast ? (
              <Link href={`/recipes/${recipe.id}`} className="btn btn-primary btn-lg">
                <CheckIcon size={18} /> Pronto! Avaliar a receita
              </Link>
            ) : (
              <button type="button" className="btn btn-primary btn-lg" onClick={() => setIndex((i) => i + 1)}>
                Próximo <ChevronRightIcon size={18} />
              </button>
            )}
          </div>
        </section>

        <aside className="cook-side">
          {timers.length > 0 && (
            <div>
              <h2 style={{ marginBottom: 10 }}>Timers</h2>
              <div className="timer-tray">
                {timers.map((timer) => (
                  <TrayTimer
                    key={timer.id}
                    timer={timer}
                    now={now}
                    onToggle={() => toggle(timer.id)}
                    onDismiss={() => dismiss(timer.id)}
                    onGoTo={() => setIndex(Number(timer.label.replace(/\D/g, "")) - 1)}
                  />
                ))}
              </div>
            </div>
          )}

          <div>
            <h2 style={{ marginBottom: 6 }}>Ingredientes</h2>
            <p className="muted small" style={{ margin: "0 0 6px" }}>
              Marque conforme separar.
            </p>
            <ul className="ingredient-list">
              {recipe.ingredients.map((ingredient) => (
                <li key={ingredient.id} className="ingredient">
                  <label className="checkbox-label" style={{ alignItems: "flex-start" }}>
                    <input
                      type="checkbox"
                      checked={prepared.has(ingredient.id)}
                      onChange={() =>
                        setPrepared((current) => {
                          const next = new Set(current);
                          if (next.has(ingredient.id)) next.delete(ingredient.id);
                          else next.add(ingredient.id);
                          return next;
                        })
                      }
                    />
                    <span className={prepared.has(ingredient.id) ? "prepared" : undefined}>
                      {formatQuantity(ingredient.quantity, ingredient.unit)} {ingredient.name}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h2 style={{ marginBottom: 6 }}>Todos os passos</h2>
            <ol style={{ margin: 0, paddingLeft: 20 }}>
              {recipe.steps.map((s, i) => (
                <li key={s.id} style={{ marginBottom: 6 }}>
                  <button
                    type="button"
                    className={i === index ? "text-button step-link current" : "text-button step-link"}
                    aria-current={i === index ? "step" : undefined}
                    onClick={() => setIndex(i)}
                  >
                    {s.instruction.length > 70 ? `${s.instruction.slice(0, 70)}…` : s.instruction}
                  </button>
                </li>
              ))}
            </ol>
          </div>
        </aside>
      </div>
    </div>
  );
}

function TrayTimer({
  timer,
  now,
  onToggle,
  onDismiss,
  onGoTo,
}: {
  timer: KitchenTimer;
  now: number;
  onToggle: () => void;
  onDismiss: () => void;
  onGoTo: () => void;
}) {
  return (
    <div className={timer.done ? "tray-timer done" : "tray-timer"} role={timer.done ? "alert" : undefined}>
      <button type="button" className="text-button tray-timer-main" onClick={onGoTo}>
        {timer.label}
        <span className="tray-timer-clock">
          {timer.done ? "Terminou!" : formatClock(remaining(timer, now) / 1000)}
        </span>
      </button>
      {!timer.done && (
        <button
          type="button"
          className="icon-button"
          onClick={onToggle}
          aria-label={timer.endsAt === null ? "Continuar timer" : "Pausar timer"}
        >
          {timer.endsAt === null ? <PlayIcon size={16} /> : <PauseIcon size={16} />}
        </button>
      )}
      <button
        type="button"
        className={timer.done ? "btn btn-primary" : "icon-button"}
        onClick={onDismiss}
        aria-label={timer.done ? undefined : "Descartar timer"}
      >
        {timer.done ? "Desligar" : <XIcon size={16} />}
      </button>
    </div>
  );
}
