import axios from 'axios';
import {
  AlertTriangle,
  ArrowLeft,
  Calendar,
  CheckCircle2,
  DollarSign,
  Inbox,
  RefreshCw,
  User,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { RequestActionModal, type RequestActionType } from '../components/RequestActionModal';
import { ROUTES } from '../constants/routes';
import {
  acceptTrainingRequest,
  getTrainerRequestDetail,
  getTrainerRequests,
  rejectTrainingRequest,
} from '../services/discoveryService';
import type { TrainingRequestDetailResponse } from '../types/discovery';

interface LocationState {
  flashMessage?: string;
}

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
  const location = useLocation();
  const state = location.state as LocationState | null;
  const [requests, setRequests] = useState<TrainingRequestDetailResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState(state?.flashMessage ?? '');

  const [selectedRequest, setSelectedRequest] = useState<TrainingRequestDetailResponse | null>(null);
  const [modalAction, setModalAction] = useState<RequestActionType | null>(null);
  const [submittingAction, setSubmittingAction] = useState(false);
  const [actionError, setActionError] = useState('');

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

  async function handleConfirmAction(message: string | null) {
    if (!selectedRequest || !modalAction || submittingAction) return;
    setSubmittingAction(true);
    setActionError('');
    try {
      const studentName = formatStudentName(selectedRequest);
      if (modalAction === 'accept') {
        await acceptTrainingRequest(selectedRequest.id, { welcome_message: message });
        setSuccessMessage(`Solicitud de ${studentName} aceptada. El vínculo activo fue creado.`);
      } else {
        await rejectTrainingRequest(selectedRequest.id, { rejection_reason: message });
        setSuccessMessage(`Solicitud de ${studentName} rechazada.`);
      }
      setModalAction(null);
      setSelectedRequest(null);
      await loadRequests(true);
    } catch (caught: unknown) {
      if (axios.isAxiosError<{ detail?: string }>(caught)) {
        setActionError(
          caught.response?.data?.detail ?? 'No pudimos procesar la solicitud. Intentá nuevamente.',
        );
      } else {
        setActionError('No pudimos procesar la solicitud. Intentá nuevamente.');
      }
      await loadRequests(true);
    } finally {
      setSubmittingAction(false);
    }
  }

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

        {successMessage && (
          <p className="profile-success inbox-success-banner" role="status">
            <CheckCircle2 size={18} /> {successMessage}
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
                    disabled={!req.can_be_accepted || submittingAction}
                    onClick={() => {
                      setActionError('');
                      setSelectedRequest(req);
                      setModalAction('accept');
                    }}
                    title={
                      !req.can_be_accepted
                        ? 'Cupos agotados; libere un cupo para poder aceptar'
                        : 'Aceptar solicitud'
                    }
                  >
                    Aceptar
                  </button>
                  <button
                    type="button"
                    className="inbox-action-btn inbox-action-btn--reject"
                    disabled={submittingAction}
                    onClick={() => {
                      setActionError('');
                      setSelectedRequest(req);
                      setModalAction('reject');
                    }}
                  >
                    Rechazar
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      {modalAction && selectedRequest && (
        <RequestActionModal
          action={modalAction}
          studentName={formatStudentName(selectedRequest)}
          planTitle={selectedRequest.plan_title ?? 'Paquete solicitado'}
          submitting={submittingAction}
          error={actionError}
          onConfirm={handleConfirmAction}
          onClose={() => {
            if (!submittingAction) {
              setModalAction(null);
              setSelectedRequest(null);
              setActionError('');
            }
          }}
        />
      )}
    </main>
  );
}
