import { useEffect, useRef, useState } from 'react';
import '../styles/rest-timer.css';

interface RestTimerProps {
  exerciseName: string;
  durationSeconds: number;
  onFinish: () => void;
}

function alertStudent() {
  if ('vibrate' in navigator) navigator.vibrate?.([180, 80, 180]);
  try {
    const context = new window.AudioContext();
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.frequency.value = 880;
    gain.gain.value = 0.12;
    oscillator.connect(gain);
    gain.connect(context.destination);
    oscillator.start();
    oscillator.stop(context.currentTime + 0.25);
    oscillator.onended = () => void context.close();
  } catch {
    // El aviso visual sigue disponible si el navegador bloquea el sonido.
  }
}

export function RestTimer({ exerciseName, durationSeconds, onFinish }: RestTimerProps) {
  const [remaining, setRemaining] = useState(durationSeconds);
  const [paused, setPaused] = useState(false);
  const deadline = useRef(Date.now() + durationSeconds * 1000);
  const completed = useRef(false);
  const finishRef = useRef(onFinish);
  finishRef.current = onFinish;

  useEffect(() => {
    if (paused || completed.current) return undefined;
    const tick = () => {
      const left = Math.max(0, Math.ceil((deadline.current - Date.now()) / 1000));
      setRemaining(left);
      if (left === 0 && !completed.current) {
        completed.current = true;
        alertStudent();
        finishRef.current();
      }
    };
    tick();
    const interval = window.setInterval(tick, 250);
    return () => window.clearInterval(interval);
  }, [paused]);

  const pause = () => {
    setRemaining(Math.max(0, Math.ceil((deadline.current - Date.now()) / 1000)));
    setPaused(true);
  };
  const resume = () => {
    deadline.current = Date.now() + remaining * 1000;
    setPaused(false);
  };
  const restart = () => {
    completed.current = false;
    deadline.current = Date.now() + durationSeconds * 1000;
    setRemaining(durationSeconds);
    setPaused(false);
  };
  const finishEarly = () => {
    completed.current = true;
    finishRef.current();
  };
  const clock = Math.floor(remaining / 60) + ':' + String(remaining % 60).padStart(2, '0');

  return <section className="rest-timer" aria-live="polite" aria-label="Temporizador de descanso">
    <div>
      <span className="rest-timer__eyebrow">Descanso entre series</span>
      <h3>{exerciseName}</h3>
      <strong className="rest-timer__clock">{clock}</strong>
      <p>{remaining === 0 ? '¡Descanso finalizado!' : paused ? 'Temporizador pausado' : 'Tomate el tiempo indicado antes de continuar.'}</p>
    </div>
    <div className="rest-timer__actions">
      {paused ? <button type="button" onClick={resume}>Reanudar</button> : <button type="button" onClick={pause}>Pausar</button>}
      <button type="button" onClick={restart}>Reiniciar</button>
      <button type="button" onClick={finishEarly}>Finalizar descanso</button>
    </div>
  </section>;
}
