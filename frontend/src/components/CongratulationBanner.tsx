import { PartyPopper } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { getStudentAchievements, markCongratulationSeen } from '../services/achievementService';
import type { AchievementItem } from '../types/achievement';
import '../styles/achievements.css';

/** US-67 escenario 4: felicitaciones del entrenador, vistas una vez al abrir la próxima sesión. */
export function CongratulationBanner() {
  const [items, setItems] = useState<AchievementItem[]>([]);
  const seenSentRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    let active = true;
    getStudentAchievements()
      .then((overview) => {
        if (!active) return;
        const unseen = overview.unlocked.filter((item) => item.congratulation && !item.congratulation.seen_at);
        setItems(unseen);
        unseen.forEach((item) => {
          if (seenSentRef.current.has(item.id)) return;
          seenSentRef.current.add(item.id);
          void markCongratulationSeen(item.id).catch(() => {
            seenSentRef.current.delete(item.id);
          });
        });
      })
      .catch(() => undefined);
    return () => { active = false; };
  }, []);

  if (items.length === 0) return null;

  async function dismiss() {
    const remaining = items.filter((item) => !seenSentRef.current.has(item.id));
    setItems([]);
    if (remaining.length > 0) {
      await Promise.allSettled(remaining.map((item) => markCongratulationSeen(item.id)));
    }
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
