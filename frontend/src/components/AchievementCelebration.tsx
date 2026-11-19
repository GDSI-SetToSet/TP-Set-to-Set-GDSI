import { Medal } from 'lucide-react';
import { useEffect, useState } from 'react';
import { getStudentAchievements, markAchievementCelebrated } from '../services/achievementService';
import type { AchievementItem } from '../types/achievement';
import '../styles/achievements.css';

/**
 * US-67 escenario 2: logros desbloqueados con esta sesión, dentro del resumen de la sesión finalizada.
 * `registerAck` entrega a quien cierra el diálogo la función que los marca como celebrados.
 */
export function AchievementCelebration({ registerAck }: { registerAck: (ack: () => void) => void }) {
  const [items, setItems] = useState<AchievementItem[]>([]);

  useEffect(() => {
    let active = true;
    getStudentAchievements()
      .then((overview) => {
        if (!active) return;
        const pending = overview.unlocked.filter((item) => item.pending_celebration);
        setItems(pending);
        registerAck(() => { pending.forEach((item) => { void markAchievementCelebrated(item.id).catch(() => undefined); }); });
      })
      .catch(() => undefined);
    return () => { active = false; };
  }, [registerAck]);

  if (items.length === 0) return null;
  return (
    <section className="achievement-celebration" role="status" aria-labelledby="achievement-celebration-title">
      <h3 id="achievement-celebration-title">
        <Medal size={20} aria-hidden="true" /> {items.length === 1 ? '¡Logro desbloqueado!' : `¡${items.length} logros desbloqueados!`}
      </h3>
      <ul>
        {items.map((item) => (
          <li key={item.id}><strong>{item.title}</strong><span>{item.description}</span></li>
        ))}
      </ul>
    </section>
  );
}
