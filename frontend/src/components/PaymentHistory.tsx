import { Ban, Plus, RotateCcw } from 'lucide-react';
import { type FormEvent, useRef, useState } from 'react';
import { getApiErrorInfo } from '../services/errorMessage';
import { voidPayment } from '../services/paymentService';
import type { PaymentHistory as PaymentHistoryData, PaymentMutationResult, PaymentView } from '../types/payment';
import {
  PAYMENT_METHOD_LABELS,
  SUBSCRIPTION_STATUS_LABELS,
  dueDescription,
  formatDateTime,
  formatIsoDate,
  formatMoney,
} from '../utils/subscriptionFormat';
import { useDialogFocus } from './useDialogFocus';

const REASON_MIN = 5;
const REASON_MAX = 500;

interface VoidPaymentDialogProps {
  payment: PaymentView;
  onVoided: (result: PaymentMutationResult) => void;
  onClose: () => void;
}

function VoidPaymentDialog({ payment, onVoided, onClose }: VoidPaymentDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useDialogFocus(dialogRef, onClose, submitting);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (submitting) return;
    const trimmed = reason.trim();
    if (trimmed.length < REASON_MIN || trimmed.length > REASON_MAX) {
      setError('Indicá el motivo de la anulación (entre 5 y 500 caracteres).');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      onVoided(await voidPayment(payment.id, trimmed));
    } catch (requestError) {
      setError(getApiErrorInfo(requestError, 'No pudimos anular el pago. Intentá nuevamente.').message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="request-modal-backdrop" role="presentation">
      <div ref={dialogRef} className="request-modal payment-dialog" role="dialog" aria-modal="true" aria-labelledby="void-dialog-title">
        <div className="profile-heading">
          <span>ANULAR PAGO</span>
          <h2 id="void-dialog-title">
            {formatMoney(payment.amount, payment.currency)} del {formatIsoDate(payment.paid_on)}
          </h2>
          <p>
            El pago no se elimina: queda en el historial como anulado, con tu motivo, y el vencimiento se recalcula sin
            contarlo. Después podés registrar el pago corregido.
          </p>
        </div>
        <form className="profile-form request-modal__form" onSubmit={handleSubmit} noValidate>
          <label>
            Motivo de la anulación
            <textarea
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              rows={3}
              maxLength={REASON_MAX}
              placeholder="Por ejemplo: el monto se cargó mal."
              disabled={submitting}
              aria-invalid={Boolean(error)}
              aria-describedby={error ? 'void-reason-error' : undefined}
              data-autofocus
            />
            {error && <small className="field-error" id="void-reason-error" role="alert">{error}</small>}
          </label>
          <div className="payment-dialog__actions">
            <button type="submit" className="inbox-action-btn inbox-action-btn--reject" disabled={submitting}>
              {submitting ? 'Anulando…' : 'Confirmar anulación'}
            </button>
            <button type="button" className="plan-cancel" onClick={onClose} disabled={submitting}>
              Cancelar
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

interface PaymentHistoryProps {
  history: PaymentHistoryData;
  /** Abre el formulario de pago; con un pago anulado, en modo corrección. */
  onRegister: (replaces?: PaymentView) => void;
  onChanged: (result: PaymentMutationResult) => void;
}

export function PaymentHistory({ history, onRegister, onChanged }: PaymentHistoryProps) {
  const { subscription, payments } = history;
  const [voiding, setVoiding] = useState<PaymentView | null>(null);
  const [justVoided, setJustVoided] = useState<PaymentView | null>(null);
  const paidOnById = new Map(payments.map((payment) => [payment.id, payment.paid_on]));
  // Se lee del historial vigente: si la corrección ya se registró, el aviso desaparece.
  const voidedPending = justVoided ? payments.find((payment) => payment.id === justVoided.id) : undefined;

  return (
    <section className="payment-history" aria-labelledby="payment-history-title">
      <div className="payment-history__header">
        <div>
          <h2 id="payment-history-title">{subscription.student_name}</h2>
          <p className="payment-history__meta">
            {subscription.plan_title} · {formatMoney(subscription.agreed_monthly_price, subscription.currency)} por mes ·
            desde el {formatIsoDate(subscription.start_date)}
          </p>
        </div>
        <button type="button" className="profile-save" onClick={() => onRegister()}>
          <Plus size={16} aria-hidden="true" /> Registrar pago
        </button>
      </div>

      <dl className="payment-history__summary">
        <div>
          <dt>Estado</dt>
          <dd>
            <span className={`subscription-badge subscription-badge--${subscription.status.toLowerCase()}`}>
              {SUBSCRIPTION_STATUS_LABELS[subscription.status]}
            </span>
          </dd>
        </div>
        <div><dt>Vencimiento</dt><dd>{formatIsoDate(subscription.due_date)}</dd></div>
        <div><dt>Situación</dt><dd>{dueDescription(subscription)}</dd></div>
        <div><dt>Meses abonados</dt><dd>{subscription.months_paid} + el primer mes</dd></div>
      </dl>

      {voidedPending && !voidedPending.replaced_by_payment_id && (
        <div className="payment-history__notice" role="status">
          <p>Pago del {formatIsoDate(voidedPending.paid_on)} anulado. ¿Querés registrar el pago corregido?</p>
          <div className="payment-history__notice-actions">
            <button type="button" className="profile-save" onClick={() => { onRegister(voidedPending); setJustVoided(null); }}>
              <RotateCcw size={16} aria-hidden="true" /> Registrar pago corregido
            </button>
            <button type="button" className="plan-cancel" onClick={() => setJustVoided(null)}>Ahora no</button>
          </div>
        </div>
      )}

      <h3 className="payment-history__subtitle">Historial de pagos</h3>
      {payments.length === 0 ? (
        <p className="plan-empty">Todavía no registraste pagos. El primer mes se considera abonado al aceptar al alumno.</p>
      ) : (
        <ol className="payment-history__list">
          {payments.map((payment) => {
            const voided = payment.status === 'ANULADO';
            return (
              <li key={payment.id} className={`payment-item${voided ? ' payment-item--voided' : ''}`}>
                <div className="payment-item__main">
                  <p className="payment-item__amount">
                    {voided ? <del>{formatMoney(payment.amount, payment.currency)}</del> : formatMoney(payment.amount, payment.currency)}
                    {voided && <span className="payment-item__tag">Anulado</span>}
                  </p>
                  <p className="payment-item__detail">
                    {formatIsoDate(payment.paid_on)} · {PAYMENT_METHOD_LABELS[payment.method]} ·{' '}
                    {payment.months_covered === 1 ? '1 mes' : `${payment.months_covered} meses`}
                  </p>
                  <p className="payment-item__audit">
                    Cargado por {payment.registered_by_name} el {formatDateTime(payment.created_at)}
                  </p>
                  {payment.note && <p className="payment-item__note">{payment.note}</p>}
                  {payment.replaces_payment_id && (
                    <p className="payment-item__link">
                      Corrige al pago anulado del {formatIsoDate(paidOnById.get(payment.replaces_payment_id))}.
                    </p>
                  )}
                  {voided && (
                    <p className="payment-item__void">
                      Anulado por {payment.voided_by_name} el {formatDateTime(payment.voided_at)} · Motivo: {payment.void_reason}
                      {payment.replaced_by_payment_id
                        ? ` · Reemplazado por el pago del ${formatIsoDate(paidOnById.get(payment.replaced_by_payment_id))}`
                        : ''}
                    </p>
                  )}
                </div>
                <div className="payment-item__actions">
                  {!voided && (
                    <button type="button" className="plan-cancel" onClick={() => setVoiding(payment)}>
                      <Ban size={16} aria-hidden="true" /> Anular
                    </button>
                  )}
                  {voided && !payment.replaced_by_payment_id && (
                    <button type="button" className="plan-cancel" onClick={() => onRegister(payment)}>
                      <RotateCcw size={16} aria-hidden="true" /> Registrar corrección
                    </button>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}

      {voiding && (
        <VoidPaymentDialog
          payment={voiding}
          onClose={() => setVoiding(null)}
          onVoided={(result) => {
            setVoiding(null);
            setJustVoided(result.payment);
            onChanged(result);
          }}
        />
      )}
    </section>
  );
}
