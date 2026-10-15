"use client";

/**
 * Timers do modo cozinha.
 *
 * Cada timer guarda o instante em que termina (`endsAt`), e não "quantos
 * segundos faltam". Parece detalhe, mas decide se o timer funciona: o
 * navegador desacelera o setInterval de abas em segundo plano (para uma vez
 * por minuto, ou mais), e um contador que subtrai 1 a cada tick atrasaria
 * minutos inteiros enquanto a pessoa olha outra aba. Com `endsAt`, cada tick
 * só recalcula `endsAt - agora`, e o tempo mostrado está sempre certo.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export interface KitchenTimer {
  id: number;
  label: string;
  durationMs: number;
  /** Instante (Date.now()) em que termina; null quando pausado. */
  endsAt: number | null;
  /** Quanto faltava quando foi pausado. */
  remainingMs: number;
  done: boolean;
}

export function remaining(timer: KitchenTimer, now: number): number {
  return timer.endsAt === null ? timer.remainingMs : Math.max(0, timer.endsAt - now);
}

let nextId = 0;

export function useKitchenTimers() {
  const [timers, setTimers] = useState<KitchenTimer[]>([]);
  const [now, setNow] = useState(() => Date.now());
  const alarm = useAlarm();

  const ringing = timers.some((t) => t.done);

  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(interval);
  }, []);

  // Detecta o fim de cada timer. O alarme dispara por transição (de rodando
  // para terminado), uma vez, e não a cada tick enquanto o timer estiver em 0.
  useEffect(() => {
    const finished = timers.filter((t) => !t.done && t.endsAt !== null && t.endsAt <= now);
    if (!finished.length) return;
    setTimers((list) =>
      list.map((t) =>
        finished.some((f) => f.id === t.id) ? { ...t, done: true, endsAt: null, remainingMs: 0 } : t,
      ),
    );
    for (const timer of finished) notify(timer.label);
  }, [now, timers]);

  useEffect(() => {
    if (ringing) alarm.start();
    else alarm.stop();
  }, [ringing, alarm]);

  const start = useCallback(
    (label: string, minutes: number) => {
      // Chamado dentro de um clique: é o momento em que o navegador deixa
      // liberar o áudio e pedir permissão de notificação.
      alarm.unlock();
      requestNotificationPermission();
      const durationMs = minutes * 60_000;
      const id = ++nextId;
      setTimers((list) => [
        ...list,
        { id, label, durationMs, endsAt: Date.now() + durationMs, remainingMs: durationMs, done: false },
      ]);
      return id;
    },
    [alarm],
  );

  const toggle = useCallback((id: number) => {
    setTimers((list) =>
      list.map((t) => {
        if (t.id !== id || t.done) return t;
        return t.endsAt === null
          ? { ...t, endsAt: Date.now() + t.remainingMs }
          : { ...t, endsAt: null, remainingMs: Math.max(0, t.endsAt - Date.now()) };
      }),
    );
  }, []);

  const reset = useCallback((id: number) => {
    setTimers((list) =>
      list.map((t) => (t.id === id ? { ...t, endsAt: null, remainingMs: t.durationMs, done: false } : t)),
    );
  }, []);

  const dismiss = useCallback((id: number) => {
    setTimers((list) => list.filter((t) => t.id !== id));
  }, []);

  return { timers, now, start, toggle, reset, dismiss };
}

// ---------- Alarme ----------

/**
 * Bipes gerados com a Web Audio API — nenhum arquivo de som para baixar.
 *
 * Navegadores só deixam tocar áudio depois de um gesto do usuário (política de
 * autoplay). Por isso o AudioContext é criado e "destravado" no clique que
 * inicia o timer, e não no momento em que o alarme precisa tocar — que pode
 * ser 40 minutos depois, sem gesto nenhum por perto.
 */
function useAlarm() {
  const context = useRef<AudioContext | null>(null);
  const interval = useRef<ReturnType<typeof setInterval> | null>(null);

  const unlock = useCallback(() => {
    if (!context.current) {
      const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!Ctx) return;
      context.current = new Ctx();
    }
    void context.current.resume();
  }, []);

  const beep = useCallback(() => {
    const ctx = context.current;
    if (!ctx) return;
    for (const offset of [0, 0.25, 0.5]) {
      const oscillator = ctx.createOscillator();
      const gain = ctx.createGain();
      oscillator.frequency.value = 880;
      gain.gain.setValueAtTime(0.0001, ctx.currentTime + offset);
      gain.gain.exponentialRampToValueAtTime(0.3, ctx.currentTime + offset + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + offset + 0.18);
      oscillator.connect(gain).connect(ctx.destination);
      oscillator.start(ctx.currentTime + offset);
      oscillator.stop(ctx.currentTime + offset + 0.2);
    }
    navigator.vibrate?.([200, 100, 200]);
  }, []);

  const start = useCallback(() => {
    if (interval.current) return;
    beep();
    interval.current = setInterval(beep, 1500);
  }, [beep]);

  const stop = useCallback(() => {
    if (interval.current) clearInterval(interval.current);
    interval.current = null;
  }, []);

  useEffect(() => stop, [stop]);

  // Objeto estável: um objeto novo a cada renderização dispararia, o tempo
  // todo, os efeitos que dependem dele.
  return useMemo(() => ({ unlock, start, stop }), [unlock, start, stop]);
}

// ---------- Notificação ----------

function requestNotificationPermission() {
  if ("Notification" in window && Notification.permission === "default") {
    void Notification.requestPermission();
  }
}

function notify(label: string) {
  // Só quando a aba não está visível: com ela na frente, o alarme na tela já
  // basta, e uma notificação do sistema por cima seria ruído.
  if (document.visibilityState === "visible") return;
  if ("Notification" in window && Notification.permission === "granted") {
    new Notification("Timer terminou", { body: label, tag: `timer-${label}` });
  }
}

// ---------- Tela sempre acesa ----------

/**
 * Mantém a tela acesa enquanto o modo cozinha está aberto (Wake Lock API).
 *
 * Na cozinha a pessoa está com as mãos sujas; a tela apagar no meio do passo é
 * o tipo de detalhe que faz desistir do app. O navegador solta o bloqueio
 * sozinho quando a aba sai de foco, então ele é pedido de novo na volta.
 */
export function useWakeLock(): boolean {
  const [active, setActive] = useState(false);

  useEffect(() => {
    if (!("wakeLock" in navigator)) return;
    let sentinel: WakeLockSentinel | null = null;
    let cancelled = false;

    async function acquire() {
      try {
        sentinel = await navigator.wakeLock.request("screen");
        if (cancelled) {
          void sentinel.release();
          return;
        }
        setActive(true);
        sentinel.addEventListener("release", () => setActive(false));
      } catch {
        // Recusado (bateria fraca, aba em segundo plano): segue sem.
        setActive(false);
      }
    }

    function onVisibility() {
      if (document.visibilityState === "visible") void acquire();
    }

    void acquire();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      cancelled = true;
      document.removeEventListener("visibilitychange", onVisibility);
      void sentinel?.release();
    };
  }, []);

  return active;
}
