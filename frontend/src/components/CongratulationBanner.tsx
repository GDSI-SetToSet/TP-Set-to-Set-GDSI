import { PartyPopper } from 'lucide-react';
import { useEffect, useState } from 'react';
import { getStudentAchievements, markCongratulationSeen } from '../services/achievementService';
import type { AchievementItem } from '../types/achievement';
import '../styles/achievements.css';

/** US-67 escenario 4: felicitaciones del entrenador, una sola vez al abrir la próxima sesión. */
export function CongratulationBanner() {
  const [items, setItems] = useState<AchievementItem[]>([]);

  useEffect(() => {
    let active = true;
    getStudentAchievements()
      .then((overview) => {
        if (!active) return;
        const unseen = overview.unlocked.filter((item) => item.congratulation && !item.congratulation.seen_at);
        setItems(unseen);
      })
      .catch(() => undefined);
    return () => { active = false; };
  }, []);

  if (items.length === 0) return null;

  async function dismiss() {
    const shown = items;
    setItems([]);
    await Promise.allSettled(shown.map((item) => markCongratulationSeen(item.id)));
  }

  return (
    <section className="congratulation-banner" role="status" aria-labelledby="congratulation-banner-title">
      <h3 id="congratulation-banner-title"><PartyPopper size={20} aria-hidden="true" /> Tu entrenador te felicitó</h3>
      <ul>
        {items.map((item) => (
          <li key={item.id}>
            <strong>{item.title}</strong>
            <p>“{item.congratulation?.message}” — {item.congratulation?.trainer_name}</p>
          </li>
        ))}
      </ul>
      <button type="button" className="congratulation-banner__close" onClick={() => void dismiss()}>Gracias</button>
    </section>
  );
}
