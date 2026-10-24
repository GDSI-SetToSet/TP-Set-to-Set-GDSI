import { AlertTriangle, ArrowLeft, Calendar, DollarSign, Inbox, RefreshCw, User } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ROUTES } from '../constants/routes';
import { getTrainerRequestDetail, getTrainerRequests } from '../services/discoveryService';
import type { TrainingRequestDetailResponse } from '../types/discovery';

function formatStudentName(request: TrainingRequestDetailResponse): string {
  const full = [request.student?.first_name, request.student?.last_name]
    .filter(Boolean)
    .join(' ')
    .trim();
  return full || 'Alumno/a';
}

function formatDate(iso: string): string {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return iso;
  return parsed.toLocaleDateString('es-AR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

export function TrainerRequestsInboxPage() {
  const [requests, setRequests] = useState<TrainingRequestDetailResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');

  const loadRequests = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError('');
    try {
      const pendingList = await getTrainerRequests('PENDING');
      const details = await Promise.all(
        pendingList.map((item) => getTrainerRequestDetail(item.id)),
      );
      setRequests(details);
    } catch {
      setError('No pudimos cargar tus solicitudes pendientes. Intentá nuevamente.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadRequests(false);
  }, [loadRequests]);

  if (loading) {
    return (
      <main className="loading-screen">
        <span className="loading-mark" /> Cargando solicitudes pendientes…
      </main>
    );
  }

  const quotaFull = requests.length > 0 && requests.some((item) => !item.can_be_accepted);

  return (
    <main className="profile-shell profile-shell--trainer">
      <header className="profile-header">
        <Link to={ROUTES.trainerHome} className="profile-back">
          <ArrowLeft size={18} /> Volver al inicio
        </Link>
        <div className="inbox-header__actions">
          <span className="profile-status profile-status--published" aria-live="polite">
            {requests.length} {requests.length === 1 ? 'pendiente' : 'pendientes'}
          </span>
          <button
            type="button"
            className="inbox-refresh-btn"
            onClick={() => void loadRequests(true)}
            disabled={refreshing}
          >
            <RefreshCw size={16} className={refreshing ? 'spin-icon' : ''} />
            {refreshing ? 'Actualizando…' : 'Actualizar'}
          </button>
        </div>
      </header>

      <section className="profile-card">
        <div className="profile-heading">
          <span>BANDEJA DE ENTRADA</span>
          <h1>Solicitudes de alumnos</h1>
          <p>
            Evaluá el perfil, los objetivos deportivos y la información médica de cada alumno que
            solicitó entrenar con vos.
          </p>
        </div>

        {error && (
          <p className="form-alert" role="alert">
            {error}
          </p>
        )}

        {quotaFull && (
          <div className="inbox-quota-alert" role="status">
            <AlertTriangle size={18} />
            <span>Cupos agotados; libere un cupo para poder aceptar</span>
          </div>
        )}

        {requests.length === 0 ? (
          <div className="inbox-empty" role="status">
            <Inbox size={36} />
            <h2>No tenés solicitudes pendientes</h2>
            <p>Cuando un alumno te envíe una solicitud para contratar un paquete, aparecerá acá.</p>
          </div>
        ) : (
          <div className="inbox-list" aria-label="Solicitudes pendientes">
            {requests.map((req) => (
              <article key={req.id} className="inbox-card">
                <div className="inbox-card__top">
                  <div>
                    <h2 className="inbox-card__student">
                      <User size={18} /> {formatStudentName(req)}
                    </h2>
                    <span className="inbox-card__plan">
                      {req.plan_title ?? 'Paquete solicitado'}
                    </span>
                  </div>
                  <span className="plan-badge plan-badge--active">Pendiente</span>
                </div>

                <div className="inbox-card__meta">
                  <span>
                    <DollarSign size={15} /> $
                    {req.agreed_monthly_price.toLocaleString('es-AR')} {req.agreed_currency}/mes
                  </span>
                  <span>
                    <Calendar size={15} /> Enviada el {formatDate(req.created_at)}
                  </span>
                </div>

                {req.student_message && (
                  <p className="inbox-card__message">“{req.student_message}”</p>
                )}

                {!req.can_be_accepted && (
                  <p className="inbox-card__quota-warning">
                    Cupos agotados; libere un cupo para poder aceptar
                  </p>
                )}

                <div className="inbox-card__actions">
                  <Link
                    to={`/entrenador/solicitudes/${req.id}`}
                    className="profile-save inbox-card__detail-link"
                  >
                    Ver detalle y evaluar
                  </Link>
                  <button
                    type="button"
                    className="inbox-action-btn inbox-action-btn--accept"
                    disabled={!req.can_be_accepted}
                    title={
                      !req.can_be_accepted
                        ? 'Cupos agotados; libere un cupo para poder aceptar'
                        : 'Disponible en el detalle de la solicitud'
                    }
                  >
                    Aceptar
                  </button>
                  <button
                    type="button"
                    className="inbox-action-btn inbox-action-btn--reject"
                  >
                    Rechazar
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
