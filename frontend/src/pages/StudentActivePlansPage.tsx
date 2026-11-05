import { ArrowLeft, Inbox, RefreshCw } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ActivePlanCard } from '../components/ActivePlanCard';
import { NotificationBell } from '../components/NotificationBell';
import { ROUTES } from '../constants/routes';
import { getActivePlans } from '../services/discoveryService';
import type { ActivePlansResponse, NotificationItem } from '../types/discovery';

export function StudentActivePlansPage() {
  const navigate = useNavigate();
  const [activePlans, setActivePlans] = useState<ActivePlansResponse>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadActivePlans = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setActivePlans(await getActivePlans());
    } catch {
      setError('No pudimos cargar tus entrenamientos. Intentá nuevamente.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadActivePlans();
  }, [loadActivePlans]);

  function handleNotificationClick(_notification: NotificationItem) {
    navigate(ROUTES.studentActivePlans);
  }

  return (
    <main className="profile-shell">
      <header className="profile-header">
        <Link to={ROUTES.studentHome} className="profile-back">
          <ArrowLeft size={18} /> Volver al inicio
        </Link>
        <div className="student-active-plans__actions">
          <NotificationBell onNotificationClick={handleNotificationClick} />
          <button
            type="button"
            className="inbox-refresh-btn"
            onClick={() => void loadActivePlans()}
            disabled={loading}
          >
            <RefreshCw size={16} /> Actualizar
          </button>
        </div>
      </header>

      <section className="profile-card student-active-plans">
        <div className="profile-heading">
          <span>ESPACIO DEL ALUMNO</span>
          <h1>Mis entrenadores</h1>
          <p>Revisá tus solicitudes pendientes, vínculos activos, planes y mensajes de tus entrenadores.</p>
        </div>

        {loading ? (
          <div className="student-active-plans__state" role="status">Cargando tus entrenamientos…</div>
        ) : error ? (
          <div className="student-active-plans__state student-active-plans__state--error" role="alert">
            <p>{error}</p>
            <button type="button" className="inbox-refresh-btn" onClick={() => void loadActivePlans()}>
              <RefreshCw size={16} /> Reintentar
            </button>
          </div>
        ) : activePlans.length === 0 ? (
          <div className="student-active-plans__empty">
            <Inbox size={28} />
            <h2>Todavía no tenés solicitudes ni vínculos activos</h2>
            <p>Cuando solicites un plan o un entrenador acepte tu solicitud, aparecerá acá.</p>
            <Link to={ROUTES.trainerSearch} className="profile-cta">Buscar entrenadores</Link>
          </div>
        ) : (
          <div className="student-active-plans__list">
            {activePlans.map((plan, index) => (
              <ActivePlanCard
                key={plan.relationship_id ?? plan.request_id ?? plan.trainer?.id ?? index}
                plan={plan}
                onRoutineClick={() => navigate(ROUTES.studentRoutines)}
              />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
