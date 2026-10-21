import { Activity, BadgeCheck, Dumbbell, HeartPulse } from 'lucide-react';
import type { ReactNode } from 'react';
import { Brand } from './Brand';

export function AuthLayout({ children, eyebrow, title, subtitle }: {
  children: ReactNode;
  eyebrow: string;
  title: string;
  subtitle: string;
}) {
  return (
    <main className="auth-shell">
      <section className="auth-visual" aria-label="Entrenamiento conectado">
        <div className="visual-top"><Brand /><span className="visual-tag"><span className="online-dot" /> Entrená a tu ritmo</span></div>
        <div className="visual-copy">
          <div className="visual-kicker"><Activity size={15} /> TU PROGRESO, EN EQUIPO</div>
          <h1>Un paso más.<br /><em>Una repetición</em><br />a la vez.</h1>
          <p>Encontrá tu entrenador. Construí hábitos. Seguí cada avance.</p>
          <div className="visual-stat"><span className="stat-mark"><HeartPulse size={18} /></span><span><b>Constancia antes que perfección</b><small>Tu entrenamiento, acompañado.</small></span><BadgeCheck size={19} className="stat-arrow" /></div>
        </div>
        <div className="visual-footer"><span>SET TO SET</span><span>ENTRENAMIENTO CONECTADO <Dumbbell size={13} /></span></div>
        <span className="visual-orbit visual-orbit--one" /><span className="visual-orbit visual-orbit--two" />
      </section>

      <section className="auth-panel">
        <div className="mobile-brand"><Brand compact /></div>
        <div className="auth-card">
          <div className="form-heading">
            <span className="eyebrow">{eyebrow}</span>
            <h2>{title}</h2>
            <p>{subtitle}</p>
          </div>
          {children}
        </div>
        <div className="panel-footer"><span>Al continuar, aceptás nuestros términos y política de privacidad.</span><span>© 2026 Set to Set</span></div>
      </section>
    </main>
  );
}
