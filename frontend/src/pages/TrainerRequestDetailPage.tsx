import axios from 'axios';
import {
  AlertTriangle,
  ArrowLeft,
  Calendar,
  CheckCircle2,
  DollarSign,
  Download,
  FileText,
  HeartPulse,
  Phone,
  Target,
  User,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { RequestActionModal, type RequestActionType } from '../components/RequestActionModal';
import { ROUTES } from '../constants/routes';
import {
  acceptTrainingRequest,
  getStudentGoalsForTrainer,
  getStudentHealthForTrainer,
  getTrainerRequestDetail,
  rejectTrainingRequest,
} from '../services/discoveryService';
import { downloadMedicalClearance } from '../services/medicalClearanceService';
import type { StudentGoalsSummary, TrainingRequestDetailResponse } from '../types/discovery';
import {
  FITNESS_GOALS,
  HEALTH_QUESTIONS,
  type HealthQuestionKey,
  type HealthQuestionnaire,
} from '../types/student';

function formatStudentName(detail: TrainingRequestDetailResponse): string {
  const full = [detail.student?.first_name, detail.student?.last_name]
    .filter(Boolean)
    .join(' ')
    .trim();
  return full || 'Alumno/a';
}

function formatBirthDateAndAge(iso: string | null): string {
  if (!iso) return 'No informada';
  const birth = new Date(iso);
  if (Number.isNaN(birth.getTime())) return iso;
  const now = new Date();
  let age = now.getUTCFullYear() - birth.getUTCFullYear();
  const monthDiff = now.getUTCMonth() - birth.getUTCMonth();
  if (monthDiff < 0 || (monthDiff === 0 && now.getUTCDate() < birth.getUTCDate())) {
    age -= 1;
  }
  const formatted = birth.toLocaleDateString('es-AR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    timeZone: 'UTC',
  });
  return age >= 0 ? `${formatted} (${age} años)` : formatted;
}

function formatDateTime(iso: string): string {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return iso;
  return parsed.toLocaleDateString('es-AR', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  });
}

export function TrainerRequestDetailPage() {
  const { requestId } = useParams<{ requestId: string }>();
  const navigate = useNavigate();
  const [detail, setDetail] = useState<TrainingRequestDetailResponse | null>(null);
  const [goals, setGoals] = useState<StudentGoalsSummary | null>(null);
  const [questionnaire, setQuestionnaire] = useState<HealthQuestionnaire | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [healthAccessError, setHealthAccessError] = useState('');
  const [downloadingClearance, setDownloadingClearance] = useState(false);
  const [clearanceMessage, setClearanceMessage] = useState('');

  const [modalAction, setModalAction] = useState<RequestActionType | null>(null);
  const [submittingAction, setSubmittingAction] = useState(false);
  const [actionError, setActionError] = useState('');
  const [actionSuccess, setActionSuccess] = useState('');

  const loadDetail = useCallback(async (id: string) => {
    const requestData = await getTrainerRequestDetail(id);
    setDetail(requestData);
    try {
      const [goalsData, healthData] = await Promise.all([
        getStudentGoalsForTrainer(requestData.student_id),
        getStudentHealthForTrainer(requestData.student_id),
      ]);
      setGoals(goalsData);
      setQuestionnaire(healthData);
      setHealthAccessError('');
    } catch {
      setGoals(null);
      setQuestionnaire(null);
      setHealthAccessError(
        'El acceso a los objetivos y datos de salud requiere una solicitud pendiente o un vínculo activo.',
      );
    }
  }, []);

  useEffect(() => {
    if (!requestId) return;
    let active = true;
    setLoading(true);
    setError('');
    setHealthAccessError('');

    loadDetail(requestId)
      .catch((caught: unknown) => {
        if (!active) return;
        if (axios.isAxiosError<{ detail?: string }>(caught)) {
          setError(caught.response?.data?.detail ?? 'No pudimos cargar el detalle de la solicitud.');
        } else {
          setError('No pudimos cargar el detalle de la solicitud.');
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [requestId, loadDetail]);

  async function handleDownloadClearance() {
    if (!detail) return;
    setDownloadingClearance(true);
    setClearanceMessage('');
    try {
      await downloadMedicalClearance(detail.student_id, `apto-medico-${detail.student_id}.pdf`);
    } catch (caught: unknown) {
      if (axios.isAxiosError(caught) && caught.response?.status === 404) {
        setClearanceMessage('El alumno todavía no cargó un certificado de apto médico vigente.');
      } else if (axios.isAxiosError(caught) && caught.response?.status === 403) {
        setClearanceMessage('No tenés autorización para descargar el apto médico de este alumno.');
      } else {
        setClearanceMessage('No pudimos descargar el apto médico. Intentá nuevamente.');
      }
    } finally {
      setDownloadingClearance(false);
    }
  }

  async function handleConfirmAction(message: string | null) {
    if (!detail || !modalAction || submittingAction) return;
    setSubmittingAction(true);
    setActionError('');
    setActionSuccess('');
    try {
      const studentName = formatStudentName(detail);
      if (modalAction === 'accept') {
        await acceptTrainingRequest(detail.id, { welcome_message: message });
        const feedback = `Solicitud de ${studentName} aceptada. El vínculo activo fue creado.`;
        setActionSuccess(feedback);
        setModalAction(null);
        navigate(ROUTES.trainerRequests, { state: { flashMessage: feedback } });
      } else {
        await rejectTrainingRequest(detail.id, { rejection_reason: message });
        const feedback = `Solicitud de ${studentName} rechazada.`;
        setActionSuccess(feedback);
        setModalAction(null);
        navigate(ROUTES.trainerRequests, { state: { flashMessage: feedback } });
      }
    } catch (caught: unknown) {
      if (axios.isAxiosError<{ detail?: string }>(caught)) {
        setActionError(
          caught.response?.data?.detail ?? 'No pudimos procesar la solicitud. Intentá nuevamente.',
        );
      } else {
        setActionError('No pudimos procesar la solicitud. Intentá nuevamente.');
      }
      if (requestId) {
        try {
          await loadDetail(requestId);
        } catch {
          // Keep current detail if refresh fails
        }
      }
    } finally {
      setSubmittingAction(false);
    }
  }

  if (loading) {
    return (
      <main className="loading-screen">
        <span className="loading-mark" /> Cargando solicitud…
      </main>
    );
  }

  if (error || !detail) {
    return (
      <main className="profile-shell profile-shell--trainer">
        <header className="profile-header">
          <Link to={ROUTES.trainerRequests} className="profile-back">
            <ArrowLeft size={18} /> Volver a la bandeja
          </Link>
        </header>
        <section className="profile-card">
          <p className="form-alert" role="alert">
            {error || 'Solicitud no encontrada.'}
          </p>
        </section>
      </main>
    );
  }

  const questionEntries = Object.entries(HEALTH_QUESTIONS) as [HealthQuestionKey, string][];

  return (
    <main className="profile-shell profile-shell--trainer">
      <header className="profile-header">
        <Link to={ROUTES.trainerRequests} className="profile-back">
          <ArrowLeft size={18} /> Volver a la bandeja
        </Link>
        <span className="profile-status profile-status--published">
          Estado: {detail.status === 'PENDING' ? 'Pendiente' : detail.status}
        </span>
      </header>

      <section className="profile-card">
        <div className="profile-heading">
          <span>DETALLE DE SOLICITUD</span>
          <h1>{formatStudentName(detail)}</h1>
          <p>Revisá los datos del alumno y verificá que sus objetivos se alineen con tu propuesta.</p>
        </div>

        {actionSuccess && (
          <p className="profile-success" role="status">
            <CheckCircle2 size={18} /> {actionSuccess}
          </p>
        )}

        <div className="request-detail-grid">
          <div className="request-detail-box">
            <h2>
              <User size={18} /> Datos de contacto del alumno
            </h2>
            <dl className="request-detail-dl">
              <div>
                <dt>Nombre completo</dt>
                <dd>{formatStudentName(detail)}</dd>
              </div>
              <div>
                <dt>Teléfono / WhatsApp</dt>
                <dd>
                  <Phone size={14} /> {detail.student?.contact_phone ?? 'No informado'}
                </dd>
              </div>
              <div>
                <dt>Fecha de nacimiento</dt>
                <dd>{formatBirthDateAndAge(detail.student?.birth_date ?? null)}</dd>
              </div>
            </dl>
          </div>

          <div className="request-detail-box">
            <h2>
              <DollarSign size={18} /> Paquete y arancel acordado
            </h2>
            <dl className="request-detail-dl">
              <div>
                <dt>Paquete solicitado</dt>
                <dd>{detail.plan_title ?? 'Paquete mensual'}</dd>
              </div>
              <div>
                <dt>Tarifa mensual acordada</dt>
                <dd>
                  ${detail.agreed_monthly_price.toLocaleString('es-AR')} {detail.agreed_currency}/mes
                </dd>
              </div>
              <div>
                <dt>Fecha de envío</dt>
                <dd>
                  <Calendar size={14} /> {formatDateTime(detail.created_at)}
                </dd>
              </div>
            </dl>
          </div>
        </div>

        <div className="request-detail-section">
          <h2>Mensaje de presentación</h2>
          <p className="request-detail-quote">
            {detail.student_message ? `“${detail.student_message}”` : 'El alumno no incluyó un mensaje inicial.'}
          </p>
        </div>

        {healthAccessError ? (
          <p className="form-alert" role="alert">
            {healthAccessError}
          </p>
        ) : (
          <>
            <div className="request-detail-section">
              <h2>
                <Target size={18} /> Objetivos deportivos y motivación
              </h2>
              {goals && goals.fitness_goals.length > 0 ? (
                <ul className="request-goals-list">
                  {goals.fitness_goals.map((goalKey) => (
                    <li key={goalKey} className="request-goal-tag">
                      {FITNESS_GOALS[goalKey] ?? goalKey}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="request-detail-muted">Sin objetivos registrados.</p>
              )}
              <div className="request-motivation">
                <strong>Motivación personal:</strong>{' '}
                <span>{goals?.personal_motivation || 'Sin motivación adicional registrada.'}</span>
              </div>
            </div>

            <div className="request-detail-section" id="cuestionario-salud">
              <div className="request-health-header">
                <h2>
                  <HeartPulse size={18} /> Cuestionario de salud y apto médico
                </h2>
                {questionnaire && (
                  <span
                    className={`plan-badge ${
                      questionnaire.has_risk_answers ? 'quota-badge--full' : 'plan-badge--active'
                    }`}
                  >
                    {questionnaire.has_risk_answers
                      ? 'Presenta antecedentes a revisar'
                      : 'Sin alertas declaradas'}
                  </span>
                )}
              </div>

              {questionnaire ? (
                <div className="request-health-box">
                  <ul className="request-health-questions">
                    {questionEntries.map(([key, label]) => (
                      <li key={key}>
                        <span>{label}</span>
                        <strong className={questionnaire[key] ? 'answer-yes' : 'answer-no'}>
                          {questionnaire[key] ? 'Sí' : 'No'}
                        </strong>
                      </li>
                    ))}
                  </ul>
                  {questionnaire.other_medical_conditions && (
                    <p className="request-health-notes">
                      <strong>Observaciones médicas:</strong> {questionnaire.other_medical_conditions}
                    </p>
                  )}
                </div>
              ) : (
                <p className="request-detail-muted">Cuestionario de salud no disponible.</p>
              )}

              <div className="request-clearance-actions">
                <button
                  type="button"
                  className="inbox-refresh-btn"
                  onClick={() => void handleDownloadClearance()}
                  disabled={downloadingClearance}
                >
                  <Download size={16} />
                  {downloadingClearance ? 'Descargando apto médico…' : 'Descargar apto médico'}
                </button>
                <a href="#cuestionario-salud" className="profile-back">
                  <FileText size={16} /> Ver cuestionario de salud
                </a>
              </div>
              {clearanceMessage && (
                <p className="request-detail-muted" role="status">
                  {clearanceMessage}
                </p>
              )}
            </div>
          </>
        )}

        <div className="request-detail-footer">
          {!detail.can_be_accepted && detail.status === 'PENDING' && (
            <div className="inbox-quota-alert" role="status">
              <AlertTriangle size={18} />
              <span>Cupos agotados; libere un cupo para poder aceptar</span>
            </div>
          )}
          <div className="inbox-card__actions">
            <button
              type="button"
              className="profile-save"
              disabled={!detail.can_be_accepted || detail.status !== 'PENDING' || submittingAction}
              onClick={() => {
                setActionError('');
                setModalAction('accept');
              }}
              title={
                !detail.can_be_accepted
                  ? 'Cupos agotados; libere un cupo para poder aceptar'
                  : 'Aceptar solicitud'
              }
            >
              Aceptar solicitud
            </button>
            <button
              type="button"
              className="inbox-action-btn inbox-action-btn--reject"
              disabled={detail.status !== 'PENDING' || submittingAction}
              onClick={() => {
                setActionError('');
                setModalAction('reject');
              }}
            >
              Rechazar solicitud
            </button>
          </div>
        </div>
      </section>

      {modalAction && (
        <RequestActionModal
          action={modalAction}
          studentName={formatStudentName(detail)}
          planTitle={detail.plan_title ?? 'Paquete solicitado'}
          submitting={submittingAction}
          error={actionError}
          onConfirm={handleConfirmAction}
          onClose={() => {
            if (!submittingAction) {
              setModalAction(null);
              setActionError('');
            }
          }}
        />
      )}
    </main>
  );
}
