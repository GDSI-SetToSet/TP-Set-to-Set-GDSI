import { Medal } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { getStudentAchievements, markAchievementCelebrated } from '../services/achievementService';
import type { AchievementItem } from '../types/achievement';
import '../styles/achievements.css';

interface AchievementCelebrationProps {
  registerAck?: (ack: () => void) => void;
  preloadedItems?: AchievementItem[];
  onDismissed?: (celebratedIds: string[]) => void;
}

/**
 * US-67 escenario 2: logros pendientes de celebración (en resumen de sesión o en "Mi evolución").
 * Si recibe `registerAck`, carga y entrega la confirmación al cerrar el diálogo padre;
 * si recibe `preloadedItems`, reutiliza los datos ya cargados y ofrece botón descartable.
 */
export function AchievementCelebration({ registerAck, preloadedItems, onDismissed }: AchievementCelebrationProps) {
  const [items, setItems] = useState<AchievementItem[]>([]);
  const [dismissing, setDismissing] = useState(false);
  const [error, setError] = useState('');
  const closedBeforeResolveRef = useRef(false);
  const acknowledgedRef = useRef(false);

  const isPreloaded = preloadedItems !== undefined;

  useEffect(() => {
    if (isPreloaded) {
      setItems(preloadedItems.filter((item) => item.pending_celebration));
      return undefined;
    }
    let active = true;
    closedBeforeResolveRef.current = false;
    acknowledgedRef.current = false;

    const markAll = (pending: AchievementItem[]) => {
      if (acknowledgedRef.current || pending.length === 0) return;
      acknowledgedRef.current = true;
      pending.forEach((item) => {
        void markAchievementCelebrated(item.id).catch(() => undefined);
      });
    };

    registerAck?.(() => {
      closedBeforeResolveRef.current = true;
    });

    getStudentAchievements()
      .then((overview) => {
        const pending = overview.unlocked.filter((item) => item.pending_celebration);
        if (closedBeforeResolveRef.current) {
          markAll(pending);
          return;
        }
        if (!active) return;
        setItems(pending);
        registerAck?.(() => markAll(pending));
      })
      .catch(() => undefined);

    return () => {
      active = false;
    };
  }, [isPreloaded, preloadedItems, registerAck]);

  async function handleDismiss() {
    if (dismissing || items.length === 0) return;
    setDismissing(true);
    setError('');
    const results = await Promise.allSettled(items.map((item) => markAchievementCelebrated(item.id)));
    const celebratedIds = items
      .filter((_, index) => results[index]?.status === 'fulfilled')
      .map((item) => item.id);
    if (celebratedIds.length > 0) {
      onDismissed?.(celebratedIds);
      setItems((current) => current.filter((item) => !celebratedIds.includes(item.id)));
    }
    if (celebratedIds.length < items.length) {
      setError('No pudimos guardar el aviso. Intentá nuevamente.');
    }
    setDismissing(false);
  }

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
      {error && <p className="field-error" role="alert">{error}</p>}
      {isPreloaded && (
        <button
          type="button"
          className="achievement-celebration__dismiss"
          disabled={dismissing}
          onClick={() => void handleDismiss()}
        >
          {dismissing ? 'Guardando…' : '¡Genial!'}
        </button>
      )}
    </section>
  );
}
