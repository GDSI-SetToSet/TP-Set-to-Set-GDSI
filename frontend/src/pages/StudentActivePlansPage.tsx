import { ArrowLeft, Inbox, RefreshCw, X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { ActivePlanCard } from '../components/ActivePlanCard';
import { NotificationBell } from '../components/NotificationBell';
import { PaymentFormDialog } from '../components/PaymentFormDialog';
import { PaymentHistory } from '../components/PaymentHistory';
import { ROUTES, studentNotificationPath } from '../constants/routes';
import { getActivePlans } from '../services/discoveryService';
import { getStudentPaymentHistory, listStudentSubscriptions } from '../services/paymentService';
import type { ActivePlansResponse, NotificationItem } from '../types/discovery';
import type { PaymentHistory as PaymentHistoryData, SubscriptionSummary } from '../types/payment';
import '../styles/subscriptions.css';

export function StudentActivePlansPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [activePlans, setActivePlans] = useState<ActivePlansResponse>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  // US-71 / US-35: suscripción de cada vínculo, pago informado e historial (`?payments=<relationshipId>`).
  const [subscriptions, setSubscriptions] = useState<SubscriptionSummary[]>([]);
  const [subscriptionsLoaded, setSubscriptionsLoaded] = useState(false);
  const [subscriptionsError, setSubscriptionsError] = useState('');
  const [reporting, setReporting] = useState<SubscriptionSummary | null>(null);
  const [history, setHistory] = useState<PaymentHistoryData | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const [notice, setNotice] = useState('');
  const [searchParams, setSearchParams] = useSearchParams();
  const historyId = searchParams.get('payments');
  const reportPaymentId = searchParams.get('reportPayment');
  const isTerminatedContext = searchParams.get('terminated') === '1';
  const subscriptionsSeqRef = useRef(0);
  const historySeqRef = useRef(0);
  const handledReportParamRef = useRef('');

  const loadSubscriptions = useCallback(async () => {
    const seq = ++subscriptionsSeqRef.current;
    setSubscriptionsError('');
    try {
      const loaded = await listStudentSubscriptions();
      if (subscriptionsSeqRef.current === seq) {
        setSubscriptions(loaded);
        setSubscriptionsLoaded(true);
      }
    } catch {
      if (subscriptionsSeqRef.current === seq) {
        setSubscriptionsError('No pudimos cargar el estado de tus suscripciones y vencimientos.');
      }
    }
  }, []);

  const loadActivePlans = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [plansResult] = await Promise.all([
        getActivePlans(),
        loadSubscriptions(),
      ]);
      setActivePlans(plansResult);
    } catch {
      setError('No pudimos cargar tus entrenamientos. Intentá nuevamente.');
    } finally {
      setLoading(false);
    }
  }, [loadSubscriptions]);

  useEffect(() => {
    void loadActivePlans();
  }, [loadActivePlans]);

  const loadHistory = useCallback(async (relationshipId: string) => {
    const seq = ++historySeqRef.current;
    setHistoryLoading(true);
    setHistoryError('');
    try {
      const loaded = await getStudentPaymentHistory(relationshipId);
      if (historySeqRef.current === seq) {
        setHistory(loaded);
      }
    } catch {
      if (historySeqRef.current === seq) {
        setHistory(null);
        setHistoryError('No pudimos cargar el historial de pagos de este vínculo. Intentá nuevamente.');
      }
    } finally {
      if (historySeqRef.current === seq) {
        setHistoryLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    if (historyId) {
      void loadHistory(historyId);
    } else {
      historySeqRef.current += 1;
      setHistory(null);
      setHistoryError('');
      setHistoryLoading(false);
    }
  }, [historyId, location.key, loadHistory]);

  useEffect(() => {
    if (!reportPaymentId || handledReportParamRef.current === reportPaymentId) return;
    const match = subscriptions.find((item) => item.relationship_id === reportPaymentId);
    if (!match) return;
    handledReportParamRef.current = reportPaymentId;
    setReporting(match);
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete('reportPayment');
    setSearchParams(nextParams, { replace: true });
  }, [reportPaymentId, subscriptions, searchParams, setSearchParams]);

  function subscriptionFor(relationshipId: string | null | undefined): SubscriptionSummary | null {
    return subscriptions.find((item) => item.relationship_id === relationshipId) ?? null;
  }

  function handleNotificationClick(notification: NotificationItem) {
    if (
      notification.type === 'PAYMENT_CONFIRMED'
      || notification.type === 'PAYMENT_REJECTED'
      || notification.type === 'SUBSCRIPTION_TERMINATED'
    ) {
      void loadActivePlans();
    }
    navigate(studentNotificationPath(notification));
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

        {isTerminatedContext && (
          <div className="form-alert" role="status">
            <strong>Este vínculo de entrenamiento fue finalizado por tu entrenador.</strong> Podés consultar tus pagos en modo lectura abajo
            {historyId && (
              <>
                {' '}o revisar tus{' '}
                <Link to={`${ROUTES.studentMessages}?relationshipId=${encodeURIComponent(historyId)}`}>mensajes anteriores</Link>.
              </>
            )}
          </div>
        )}
        {subscriptionsError && (
          <p className="form-alert" role="alert">
            {subscriptionsError}{' '}
            <button type="button" className="inbox-refresh-btn" onClick={() => void loadSubscriptions()}>Reintentar</button>
          </p>
        )}
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
                subscription={subscriptionFor(plan.relationship_id)}
                onReportPayment={() => setReporting(subscriptionFor(plan.relationship_id))}
                onShowPayments={() => plan.relationship_id && setSearchParams({ payments: plan.relationship_id })}
              />
            ))}
          </div>
        )}
        {notice && <p className="form-alert form-alert--success" role="status">{notice}</p>}
      </section>

      {historyId && (
        <div className="profile-card subscriptions__history">
          <button type="button" className="subscriptions__close" onClick={() => setSearchParams({})} aria-label="Cerrar historial de pagos">
            <X size={18} aria-hidden="true" />
          </button>
          {historyLoading ? (
            <p role="status">Cargando historial de pagos…</p>
          ) : historyError ? (
            <div className="form-alert" role="alert">
              <p>{historyError}</p>
              <button type="button" className="inbox-refresh-btn" onClick={() => void loadHistory(historyId)}>
                <RefreshCw size={16} /> Reintentar
              </button>
            </div>
          ) : history ? (
            <PaymentHistory
              viewer="student"
              history={history}
              readOnly={isTerminatedContext || (subscriptionsLoaded && !subscriptionFor(history.subscription.relationship_id))}
              onRegister={() => setReporting(history.subscription)}
              onChanged={() => void loadHistory(historyId)}
            />
          ) : null}
        </div>
      )}

      {reporting && (
        <PaymentFormDialog
          mode="student"
          subscription={reporting}
          onClose={() => setReporting(null)}
          onSaved={(result) => {
            setReporting(null);
            setNotice(`Pago informado a ${result.subscription.trainer_name}. Queda pendiente hasta que lo confirme.`);
            void loadSubscriptions();
            if (historyId === result.subscription.relationship_id) void loadHistory(historyId);
          }}
        />
      )}
    </main>
  );
}
