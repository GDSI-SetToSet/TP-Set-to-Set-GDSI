import { Lock, Medal, Pin } from 'lucide-react';
import type { AchievementsOverview } from '../types/achievement';
import { formatAchievementDate } from '../utils/achievementFormat';
import '../styles/achievements.css';

interface AchievementsSectionProps {
  overview: AchievementsOverview;
}

/** US-67 escenario 3: logros desbloqueados con su fecha y avance de los que faltan. */
export function AchievementsSection({ overview }: AchievementsSectionProps) {
  const { unlocked, locked } = overview;
  return (
    <section className="achievements" aria-labelledby="achievements-title">
      <h4 id="achievements-title"><Medal size={18} aria-hidden="true" /> Mis logros</h4>
      <p className="achievements__summary">
        {unlocked.length === 0
          ? 'Todavía no desbloqueaste logros. Completá tu primera sesión para empezar.'
          : `${unlocked.length} de ${unlocked.length + locked.length} logros desbloqueados.`}
      </p>
      <ul className="achievements__grid">
        {unlocked.map((item) => (
          <li key={item.code} className="achievement achievement--unlocked">
            <Medal size={22} aria-hidden="true" />
            <div>
              <strong>{item.title}</strong>
              <span>{item.description}</span>
              <small>Obtenido el {formatAchievementDate(item.unlocked_at)}</small>
              {item.congratulation && (
                <p className="achievement__congratulation">
                  <Pin size={13} aria-hidden="true" /> {item.congratulation.trainer_name}: “{item.congratulation.message}”
                </p>
              )}
            </div>
          </li>
        ))}
        {locked.map((item) => (
          <li key={item.code} className="achievement achievement--locked">
            <Lock size={22} aria-hidden="true" />
            <div>
              <strong>{item.title}</strong>
              <span>{item.description}</span>
              <small>Bloqueado · {item.current} de {item.target}</small>
              <progress value={item.current} max={item.target} aria-label={`Avance de ${item.title}`} />
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
