import { ArrowLeft, History, Plus, RefreshCw, X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { PaymentFormDialog } from '../components/PaymentFormDialog';
import { PaymentHistory } from '../components/PaymentHistory';
import { ROUTES } from '../constants/routes';
import { getApiErrorInfo } from '../services/errorMessage';
import { getPaymentHistory, listSubscriptions } from '../services/paymentService';
import type {
  PaymentHistory as PaymentHistoryData,
  PaymentView,
  SubscriptionStatus,
  SubscriptionSummary,
} from '../types/payment';
import {
  SUBSCRIPTION_STATUS_LABELS,
  dueDescription,
  formatIsoDate,
  formatMoney,
} from '../utils/subscriptionFormat';
import '../styles/subscriptions.css';

type Filter = 'ALL' | SubscriptionStatus;

const FILTERS: { value: Filter; label: string }[] = [
  { value: 'ALL', label: 'Todas' },
  { value: 'VENCIDA', label: 'Vencidas' },
  { value: 'POR_VENCER', label: 'Por vencer' },
  { value: 'AL_DIA', label: 'Al día' },
];

interface FormTarget {
  subscription: SubscriptionSummary;
  replaces: PaymentView | null;
}

export function TrainerSubscriptionsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedStudentId = searchParams.get('studentId');
  const [items, setItems] = useState<SubscriptionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<Filter>('ALL');
  const [history, setHistory] = useState<PaymentHistoryData | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const [formTarget, setFormTarget] = useState<FormTarget | null>(null);
  const [savedMessage, setSavedMessage] = useState('');
  const listRequestRef = useRef(0);
  const historyRequestRef = useRef(0);
  const historyRef = useRef<HTMLDivElement>(null);

  const loadList = useCallback(() => {
    const requestId = ++listRequestRef.current;
    setLoading(true);
    setError('');
    listSubscriptions()
      .then((loaded) => {
        if (listRequestRef.current === requestId) setItems(loaded);
      })
      .catch(() => {
        if (listRequestRef.current === requestId) setError('No pudimos cargar las suscripciones. Intentá nuevamente.');
      })
      .finally(() => {
        if (listRequestRef.current === requestId) setLoading(false);
      });
  }, []);

  const loadHistory = useCallback((studentId: string) => {
    const requestId = ++historyRequestRef.current;
    setHistoryLoading(true);
    setHistoryError('');
    getPaymentHistory(studentId)
      .then((loaded) => {
        if (historyRequestRef.current === requestId) setHistory(loaded);
      })
      .catch((requestError) => {
        if (historyRequestRef.current === requestId) {
          setHistory(null);
          setHistoryError(getApiErrorInfo(requestError, 'No pudimos cargar el historial de pagos.').message);
        }
      })
      .finally(() => {
        if (historyRequestRef.current === requestId) setHistoryLoading(false);
      });
  }, []);

  useEffect(() => {
    loadList();
  }, [loadList]);

  useEffect(() => {
    if (selectedStudentId) loadHistory(selectedStudentId);
    else setHistory(null);
  }, [selectedStudentId, loadHistory]);

  const historyKey = history?.subscription.relationship_id;
  useEffect(() => {
    if (historyKey && selectedStudentId) historyRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
  }, [historyKey, selectedStudentId]);

  function openHistory(studentId: string) {
    setSavedMessage('');
    setSearchParams({ studentId });
  }

  function closeHistory() {
    setSearchParams({});
  }

  function refreshAfterChange(studentId: string) {
    loadList();
    if (selectedStudentId === studentId) loadHistory(studentId);
  }

  const visible = filter === 'ALL' ? items : items.filter((item) => item.status === filter);
  const counts = {
    VENCIDA: items.filter((item) => item.status === 'VENCIDA').length,
    POR_VENCER: items.filter((item) => item.status === 'POR_VENCER').length,
    AL_DIA: items.filter((item) => item.status === 'AL_DIA').length,
  };

  return (
    <main className="profile-shell profile-shell--trainer">
      <header className="profile-header">
        <Link to={ROUTES.trainerHome} className="profile-back"><ArrowLeft size={18} /> Volver al inicio</Link>
      </header>

      <section className="profile-card subscriptions">
        <div className="profile-heading">
          <span>PAGOS</span>
          <h1>Suscripciones</h1>
          <p>Controlá quién está al día, registrá los pagos que recibís por fuera de la app y consultá el historial de cada alumno.</p>
        </div>

        {savedMessage && <p className="form-alert form-alert--success" role="status">{savedMessage}</p>}

        <div className="subscriptions__toolbar">
          <div className="subscriptions__filters" role="group" aria-label="Filtrar por estado">
            {FILTERS.map((option) => (
              <button
                key={option.value}
                type="button"
                className={`subscriptions__filter${filter === option.value ? ' is-active' : ''}`}
                aria-pressed={filter === option.value}
                onClick={() => setFilter(option.value)}
              >
                {option.label}
                {option.value !== 'ALL' && !loading && <span className="subscriptions__count">{counts[option.value]}</span>}
              </button>
            ))}
          </div>
          <button type="button" className="subscriptions__refresh" onClick={loadList} disabled={loading}>
            <RefreshCw size={16} aria-hidden="true" /> Actualizar
          </button>
        </div>

        {loading ? (
          <p role="status">Cargando suscripciones…</p>
        ) : error ? (
          <p className="form-alert" role="alert">{error}</p>
        ) : items.length === 0 ? (
          <p className="plan-empty">Todavía no tenés alumnos activos.</p>
        ) : visible.length === 0 ? (
          <p className="plan-empty">No hay suscripciones en este estado.</p>
        ) : (
          <ul className="subscriptions__list">
            {visible.map((item) => (
              <li
                key={item.relationship_id}
                className={`subscription-row subscription-row--${item.status.toLowerCase()}${
                  selectedStudentId === item.student_id ? ' is-selected' : ''
                }`}
              >
                <div className="subscription-row__main">
                  <p className="subscription-row__name">{item.student_name}</p>
                  <p className="subscription-row__plan">
                    {item.plan_title} · {formatMoney(item.agreed_monthly_price, item.currency)} por mes
                  </p>
                  <p className="subscription-row__dates">
                    Vence el <strong>{formatIsoDate(item.due_date)}</strong>
                    {' · '}
                    {item.last_payment_on ? `Último pago: ${formatIsoDate(item.last_payment_on)}` : 'Sin pagos registrados'}
                  </p>
                </div>
                <div className="subscription-row__status">
                  <span className={`subscription-badge subscription-badge--${item.status.toLowerCase()}`}>
                    {SUBSCRIPTION_STATUS_LABELS[item.status]}
                  </span>
                  <span className="subscription-row__due">{dueDescription(item)}</span>
                  {item.pending_payment_count > 0 && (
                    <span className="subscription-row__pending">
                      {item.pending_payment_count === 1 ? '1 pago por confirmar' : `${item.pending_payment_count} pagos por confirmar`}
                    </span>
                  )}
                </div>
                <div className="subscription-row__actions">
                  <button
                    type="button"
                    className="profile-save"
                    onClick={() => setFormTarget({ subscription: item, replaces: null })}
                    aria-label={`Registrar pago de ${item.student_name}`}
                  >
                    <Plus size={16} aria-hidden="true" /> Registrar pago
                  </button>
                  <button
                    type="button"
                    className="plan-cancel"
                    onClick={() => openHistory(item.student_id)}
                    aria-label={`Ver historial de pagos de ${item.student_name}`}
                  >
                    <History size={16} aria-hidden="true" /> Ver historial
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {selectedStudentId && (
        <div ref={historyRef} className="profile-card subscriptions__history">
          <button type="button" className="subscriptions__close" onClick={closeHistory} aria-label="Cerrar historial">
            <X size={18} aria-hidden="true" />
          </button>
          {historyLoading && !history ? (
            <p role="status">Cargando historial de pagos…</p>
          ) : historyError ? (
            <p className="form-alert" role="alert">{historyError}</p>
          ) : history ? (
            <PaymentHistory
              history={history}
              onRegister={(replaces) => setFormTarget({ subscription: history.subscription, replaces: replaces ?? null })}
              onChanged={(result) => refreshAfterChange(result.subscription.student_id)}
            />
          ) : null}
        </div>
      )}

      {formTarget && (
        <PaymentFormDialog
          subscription={formTarget.subscription}
          replaces={formTarget.replaces}
          onClose={() => setFormTarget(null)}
          onSaved={(result) => {
            setFormTarget(null);
            setSavedMessage(
              `Pago registrado. ${result.subscription.student_name} vence el ${formatIsoDate(result.subscription.due_date)}.`,
            );
            refreshAfterChange(result.subscription.student_id);
          }}
        />
      )}
    </main>
  );
}
