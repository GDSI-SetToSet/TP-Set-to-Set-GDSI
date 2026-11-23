import { Ban, Check, Paperclip, Plus, RotateCcw, X } from 'lucide-react';
import { type FormEvent, useRef, useState } from 'react';
import { getApiErrorInfo } from '../services/errorMessage';
import { confirmPayment, downloadReceipt, rejectPayment, voidPayment } from '../services/paymentService';
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

type ReasonKind = 'void' | 'reject';

const REASON_COPY: Record<ReasonKind, { kicker: string; description: string; label: string; error: string; submit: string; busy: string; fallback: string }> = {
  void: {
    kicker: 'ANULAR PAGO',
    description:
      'El pago no se elimina: queda en el historial como anulado, con tu motivo, y el vencimiento se recalcula sin contarlo. Después podés registrar el pago corregido.',
    label: 'Motivo de la anulación',
    error: 'Indicá el motivo de la anulación (entre 5 y 500 caracteres).',
    submit: 'Confirmar anulación',
    busy: 'Anulando…',
    fallback: 'No pudimos anular el pago. Intentá nuevamente.',
  },
  reject: {
    kicker: 'RECHAZAR PAGO INFORMADO',
    description: 'El pago queda rechazado con tu motivo y el vencimiento no cambia. El alumno recibe una notificación con el motivo.',
    label: 'Motivo del rechazo',
    error: 'Indicá el motivo del rechazo (entre 5 y 500 caracteres).',
    submit: 'Confirmar rechazo',
    busy: 'Rechazando…',
    fallback: 'No pudimos rechazar el pago. Intentá nuevamente.',
  },
};

interface ReasonDialogProps {
  kind: ReasonKind;
  payment: PaymentView;
  onDone: (result: PaymentMutationResult) => void;
  onClose: () => void;
}

/** Anular (US-34) o rechazar (US-71) un pago: los dos exigen un motivo. */
function PaymentReasonDialog({ kind, payment, onDone, onClose }: ReasonDialogProps) {
  const copy = REASON_COPY[kind];
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
      setError(copy.error);
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      onDone(kind === 'void' ? await voidPayment(payment.id, trimmed) : await rejectPayment(payment.id, trimmed));
    } catch (requestError) {
      setError(getApiErrorInfo(requestError, copy.fallback).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="request-modal-backdrop" role="presentation">
      <div ref={dialogRef} className="request-modal payment-dialog" role="dialog" aria-modal="true" aria-labelledby="reason-dialog-title">
        <div className="profile-heading">
          <span>{copy.kicker}</span>
          <h2 id="reason-dialog-title">
            {formatMoney(payment.amount, payment.currency)} del {formatIsoDate(payment.paid_on)}
          </h2>
          <p>{copy.description}</p>
        </div>
        <form className="profile-form request-modal__form" onSubmit={handleSubmit} noValidate>
          <label>
            {copy.label}
            <textarea
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              rows={3}
              maxLength={REASON_MAX}
              disabled={submitting}
              aria-invalid={Boolean(error)}
              aria-describedby={error ? 'reason-dialog-error' : undefined}
              data-autofocus
            />
            {error && <small className="field-error" id="reason-dialog-error" role="alert">{error}</small>}
          </label>
          <div className="payment-dialog__actions">
            <button type="submit" className="inbox-action-btn inbox-action-btn--reject" disabled={submitting}>
              {submitting ? copy.busy : copy.submit}
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

const STATUS_TAGS: Partial<Record<PaymentView['status'], { label: string; className: string }>> = {
  ANULADO: { label: 'Anulado', className: 'payment-item__tag' },
  PENDIENTE_CONFIRMACION: { label: 'Pendiente de confirmación', className: 'payment-item__tag payment-item__tag--pending' },
  RECHAZADO: { label: 'Rechazado', className: 'payment-item__tag payment-item__tag--rejected' },
};

interface PaymentHistoryProps {
  history: PaymentHistoryData;
  /** Abre el formulario de pago; con un pago anulado, en modo corrección (solo entrenador). */
  onRegister: (replaces?: PaymentView) => void;
  onChanged: (result: PaymentMutationResult) => void;
  /** US-71: el alumno ve el historial sin acciones de revisión y "Informar pago" en lugar de "Registrar pago". */
  viewer?: 'trainer' | 'student';
  /** US-35: oculta acciones de carga cuando el vínculo fue dado de baja (solo lectura). */
  readOnly?: boolean;
}

export function PaymentHistory({ history, onRegister, onChanged, viewer = 'trainer', readOnly = false }: PaymentHistoryProps) {
  const isTrainer = viewer === 'trainer';
  const { subscription, payments } = history;
  const [reasonTarget, setReasonTarget] = useState<{ kind: ReasonKind; payment: PaymentView } | null>(null);
  const [justVoided, setJustVoided] = useState<PaymentView | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState('');
  const paidOnById = new Map(payments.map((payment) => [payment.id, payment.paid_on]));
  // Se lee del historial vigente: si la corrección ya se registró, el aviso desaparece.
  const voidedPending = justVoided ? payments.find((payment) => payment.id === justVoided.id) : undefined;

  async function handleConfirm(payment: PaymentView) {
    setBusyId(payment.id);
    setActionError('');
    try {
      onChanged(await confirmPayment(payment.id));
    } catch (error) {
      setActionError(getApiErrorInfo(error, 'No pudimos confirmar el pago. Intentá nuevamente.').message);
    } finally {
      setBusyId(null);
    }
  }

  async function handleReceipt(payment: PaymentView) {
    setActionError('');
    try {
      await downloadReceipt(payment.id, payment.receipt_filename);
    } catch {
      setActionError('No pudimos descargar el comprobante. Intentá nuevamente.');
    }
  }

  return (
    <section className="payment-history" aria-labelledby="payment-history-title">
      <div className="payment-history__header">
        <div>
          <h2 id="payment-history-title">{isTrainer ? subscription.student_name : `Tu suscripción con ${subscription.trainer_name}`}</h2>
          <p className="payment-history__meta">
            {subscription.plan_title} · {formatMoney(subscription.agreed_monthly_price, subscription.currency)} por mes ·
            desde el {formatIsoDate(subscription.start_date)}
          </p>
        </div>
        {!readOnly && (
          <button type="button" className="profile-save" onClick={() => onRegister()}>
            <Plus size={16} aria-hidden="true" /> {isTrainer ? 'Registrar pago' : 'Informar pago'}
          </button>
        )}
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

      {actionError && <p className="form-alert" role="alert">{actionError}</p>}

      {isTrainer && voidedPending && !voidedPending.replaced_by_payment_id && (
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
        <p className="plan-empty">
          {isTrainer
            ? 'Todavía no registraste pagos. El primer mes se considera abonado al aceptar al alumno.'
            : 'Todavía no hay pagos registrados. El primer mes se considera abonado al empezar.'}
        </p>
      ) : (
        <ol className="payment-history__list">
          {payments.map((payment) => {
            const voided = payment.status === 'ANULADO';
            const closed = voided || payment.status === 'RECHAZADO';
            const tag = STATUS_TAGS[payment.status];
            return (
              <li key={payment.id} className={`payment-item${closed ? ' payment-item--voided' : ''}${payment.status === 'PENDIENTE_CONFIRMACION' ? ' payment-item--pending' : ''}`}>
                <div className="payment-item__main">
                  <p className="payment-item__amount">
                    {closed ? <del>{formatMoney(payment.amount, payment.currency)}</del> : formatMoney(payment.amount, payment.currency)}
                    {tag && <span className={tag.className}>{tag.label}</span>}
                  </p>
                  <p className="payment-item__detail">
                    {formatIsoDate(payment.paid_on)} · {PAYMENT_METHOD_LABELS[payment.method]} ·{' '}
                    {payment.months_covered === 1 ? '1 mes' : `${payment.months_covered} meses`}
                  </p>
                  <p className="payment-item__audit">
                    {payment.source === 'STUDENT' ? 'Informado por' : 'Cargado por'} {payment.registered_by_name} el {formatDateTime(payment.created_at)}
                    {payment.confirmed_by_name && ` · Confirmado por ${payment.confirmed_by_name} el ${formatDateTime(payment.confirmed_at)}`}
                  </p>
                  {payment.note && <p className="payment-item__note">{payment.note}</p>}
                  {payment.replaces_payment_id && (
                    <p className="payment-item__link">
                      Corrige al pago anulado del {formatIsoDate(paidOnById.get(payment.replaces_payment_id))}.
                    </p>
                  )}
                  {payment.status === 'RECHAZADO' && (
                    <p className="payment-item__void">
                      Rechazado por {payment.rejected_by_name} el {formatDateTime(payment.rejected_at)} · Motivo: {payment.rejection_reason}
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
                  {payment.has_receipt && (
                    <button type="button" className="plan-cancel" onClick={() => void handleReceipt(payment)}>
                      <Paperclip size={16} aria-hidden="true" /> Comprobante
                    </button>
                  )}
                  {isTrainer && payment.status === 'PENDIENTE_CONFIRMACION' && (
                    <>
                      <button type="button" className="profile-save" disabled={busyId === payment.id} onClick={() => void handleConfirm(payment)}>
                        <Check size={16} aria-hidden="true" /> {busyId === payment.id ? 'Confirmando…' : 'Confirmar'}
                      </button>
                      <button type="button" className="plan-cancel" onClick={() => setReasonTarget({ kind: 'reject', payment })}>
                        <X size={16} aria-hidden="true" /> Rechazar
                      </button>
                    </>
                  )}
                  {isTrainer && payment.status === 'CONFIRMADO' && (
                    <button type="button" className="plan-cancel" onClick={() => setReasonTarget({ kind: 'void', payment })}>
                      <Ban size={16} aria-hidden="true" /> Anular
                    </button>
                  )}
                  {isTrainer && voided && !payment.replaced_by_payment_id && (
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

      {reasonTarget && (
        <PaymentReasonDialog
          kind={reasonTarget.kind}
          payment={reasonTarget.payment}
          onClose={() => setReasonTarget(null)}
          onDone={(result) => {
            if (reasonTarget.kind === 'void') setJustVoided(result.payment);
            setReasonTarget(null);
            onChanged(result);
          }}
        />
      )}
    </section>
  );
}
