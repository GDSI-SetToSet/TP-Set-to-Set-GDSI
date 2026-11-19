import { Flame } from 'lucide-react';
import type { TrainingStreak } from '../types/studentProgress';
import '../styles/streak.css';

export function weeksLabel(weeks: number): string {
  return weeks === 1 ? '1 semana' : `${weeks} semanas`;
}

/** Texto corto para el acceso "Rutina del día" del inicio (US-68 escenario 4). */
export function streakSummary(streak: TrainingStreak): string {
  return `Racha: ${weeksLabel(streak.current_weeks)} · ${streak.this_week_sessions} de ${streak.weekly_target} sesiones esta semana`;
}

interface StreakCardProps {
  streak: TrainingStreak;
  /** Alumno: "tu racha"; entrenador: racha del alumno. */
  perspective?: 'student' | 'trainer';
}

/** US-68 escenario 3: racha actual, máxima y avance de la semana en curso. */
export function StreakCard({ streak, perspective = 'student' }: StreakCardProps) {
  if (!streak.has_routine) {
    return (
      <section className="streak-card streak-card--empty" aria-label="Racha de constancia">
        <Flame size={20} aria-hidden="true" />
        <p>{perspective === 'student' ? 'Tu racha empieza cuando tengas una rutina asignada.' : 'Sin rutina asignada: todavía no hay racha.'}</p>
      </section>
    );
  }
  const remaining = Math.max(streak.weekly_target - streak.this_week_sessions, 0);
  return (
    <section className="streak-card" aria-label="Racha de constancia">
      <div className="streak-card__main">
        <Flame size={24} aria-hidden="true" className={streak.current_weeks > 0 ? 'streak-card__flame--on' : 'streak-card__flame'} />
        <div>
          <p className="streak-card__value">{weeksLabel(streak.current_weeks)}</p>
          <p className="streak-card__label">{perspective === 'student' ? 'Tu racha actual' : 'Racha actual'}</p>
        </div>
      </div>
      <dl className="streak-card__stats">
        <div><dt>Racha máxima</dt><dd>{weeksLabel(streak.max_weeks)}</dd></div>
        <div>
          <dt>Esta semana</dt>
          <dd>{streak.this_week_sessions} de {streak.weekly_target} sesiones</dd>
        </div>
      </dl>
      <p className="streak-card__hint">
        {remaining > 0
          ? `${remaining === 1 ? 'Falta 1 sesión' : `Faltan ${remaining} sesiones`} para que esta semana sume a la racha (se cuenta al terminar el domingo).`
          : 'Esta semana ya cumple el objetivo: suma a la racha cuando termine el domingo.'}
      </p>
    </section>
  );
}
