import { type FormEvent, useRef, useState } from 'react';
import { getApiErrorInfo } from '../services/errorMessage';
import { getFieldErrors, registerPayment, reportPayment } from '../services/paymentService';
import type { PaymentMethod, PaymentMutationResult, PaymentView, SubscriptionSummary } from '../types/payment';
import { localDateInputValue } from '../utils/dailyRoutineFormat.mjs';
import { PAYMENT_METHOD_LABELS, formatIsoDate, formatMoney, suggestedAmount } from '../utils/subscriptionFormat';
import { useDialogFocus } from './useDialogFocus';

interface PaymentFormDialogProps {
  subscription: SubscriptionSummary;
  /** Pago anulado que este registro corrige (escenario 6). */
  replaces?: PaymentView | null;
  onSaved: (result: PaymentMutationResult) => void;
  onClose: () => void;
  /** US-71: el alumno informa el pago (queda pendiente) y puede adjuntar un comprobante. */
  mode?: 'trainer' | 'student';
}

const RECEIPT_TYPES = ['application/pdf', 'image/jpeg', 'image/png'];
const RECEIPT_MAX_BYTES = 10 * 1024 * 1024;

type FieldName = 'paid_on' | 'amount' | 'method' | 'months_covered' | 'note';
type FieldErrors = Partial<Record<FieldName | 'replaces_payment_id' | 'receipt', string>>;

const MONTH_OPTIONS = Array.from({ length: 12 }, (_, index) => index + 1);
const NOTE_MAX = 500;
const AMOUNT_PATTERN = /^\d+(\.\d{1,2})?$/;

function normalizeAmount(value: string): string {
  return value.trim().replace(/\s/g, '').replace(',', '.');
}

/** Mismas reglas y mensajes que el backend (research.md R5), todas a la vez. */
function validate(paidOn: string, amount: string, method: string, months: number, note: string): FieldErrors {
  const errors: FieldErrors = {};
  const today = localDateInputValue();
  if (!paidOn) errors.paid_on = 'Ingresá la fecha del pago.';
  else if (paidOn > today) errors.paid_on = 'La fecha del pago no puede ser futura.';

  const normalized = normalizeAmount(amount);
  if (!normalized) errors.amount = 'Ingresá el monto del pago.';
  else if (Number.isNaN(Number(normalized))) errors.amount = 'Ingresá el monto del pago.';
  else if (Number(normalized) <= 0) errors.amount = 'El monto debe ser mayor a cero.';
  else if (Number(normalized) > 9999999.99) errors.amount = 'El monto no puede superar $9.999.999,99.';
  else if (!AMOUNT_PATTERN.test(normalized)) errors.amount = 'El monto admite hasta 2 decimales.';

  if (!method) errors.method = 'Elegí el medio de pago.';
  if (!Number.isInteger(months) || months < 1 || months > 12) errors.months_covered = 'El período debe ser de 1 a 12 meses.';
  if (note.trim().length > NOTE_MAX) errors.note = 'La nota admite hasta 500 caracteres.';
  return errors;
}

export function PaymentFormDialog({ subscription, replaces = null, onSaved, onClose, mode = 'trainer' }: PaymentFormDialogProps) {
  const isStudent = mode === 'student';
  const [receipt, setReceipt] = useState<File | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const [paidOn, setPaidOn] = useState(replaces?.paid_on ?? localDateInputValue());
  const [months, setMonths] = useState(replaces?.months_covered ?? 1);
  const [amount, setAmount] = useState(
    replaces ? Number(replaces.amount).toFixed(2) : suggestedAmount(subscription.agreed_monthly_price, 1),
  );
  // Mientras el entrenador no edite el monto, sigue a tarifa × meses.
  const [amountTouched, setAmountTouched] = useState(Boolean(replaces));
  const [method, setMethod] = useState<PaymentMethod | ''>(replaces?.method ?? '');
  const [note, setNote] = useState(replaces?.note ?? '');
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useDialogFocus(dialogRef, onClose, submitting);

  function changeMonths(value: number) {
    setMonths(value);
    if (!amountTouched) setAmount(suggestedAmount(subscription.agreed_monthly_price, value));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (submitting) return;
    const found = validate(paidOn, amount, method, months, note);
    if (receipt && (!RECEIPT_TYPES.includes(receipt.type) || receipt.size > RECEIPT_MAX_BYTES)) {
      found.receipt = 'El comprobante debe ser un PDF, JPG o PNG de hasta 10 MB.';
    }
    setErrors(found);
    setFormError('');
    if (Object.keys(found).length > 0) return;

    setSubmitting(true);
    try {
      const payload = {
        paid_on: paidOn,
        amount: normalizeAmount(amount),
        method: method as PaymentMethod,
        months_covered: months,
        note: note.trim() || null,
        replaces_payment_id: replaces?.id ?? null,
      };
      const result = isStudent
        ? await reportPayment(subscription.relationship_id, payload, receipt)
        : await registerPayment(subscription.student_id, payload);
      onSaved(result);
    } catch (error) {
      const fieldErrors = getFieldErrors(error) as FieldErrors;
      setErrors(fieldErrors);
      if (Object.keys(fieldErrors).length === 0 || fieldErrors.replaces_payment_id) {
        setFormError(
          fieldErrors.replaces_payment_id
            ?? getApiErrorInfo(error, 'No pudimos registrar el pago. Intentá nuevamente.').message,
        );
      }
    } finally {
      setSubmitting(false);
    }
  }

  const fieldProps = (name: FieldName) => ({
    'aria-invalid': Boolean(errors[name]),
    'aria-describedby': errors[name] ? `payment-${name}-error` : undefined,
  });
  const fieldError = (name: FieldName) => errors[name]
    ? <small className="field-error" id={`payment-${name}-error`}>{errors[name]}</small>
    : null;

  return (
    <div className="request-modal-backdrop" role="presentation">
      <div
        ref={dialogRef}
        className="request-modal payment-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="payment-dialog-title"
      >
        <div className="profile-heading">
          <span>{isStudent ? 'INFORMAR PAGO' : replaces ? 'CORREGIR PAGO' : 'REGISTRAR PAGO'}</span>
          <h2 id="payment-dialog-title">{isStudent ? `Pago a ${subscription.trainer_name}` : subscription.student_name}</h2>
          <p>
            {subscription.plan_title} · {formatMoney(subscription.agreed_monthly_price, subscription.currency)} por mes ·
            vence el {formatIsoDate(subscription.due_date)}
          </p>
          {replaces && (
            <p className="payment-dialog__replaces">
              Corrige al pago anulado del {formatIsoDate(replaces.paid_on)}.
            </p>
          )}
        </div>

        <form className="profile-form request-modal__form payment-dialog__form" onSubmit={handleSubmit} noValidate>
          <label>
            Fecha del pago
            <input
              type="date"
              value={paidOn}
              max={localDateInputValue()}
              onChange={(event) => setPaidOn(event.target.value)}
              disabled={submitting}
              data-autofocus
              {...fieldProps('paid_on')}
            />
            {fieldError('paid_on')}
          </label>

          <div className="payment-dialog__row">
            <label>
              Meses abonados
              <select
                value={months}
                onChange={(event) => changeMonths(Number(event.target.value))}
                disabled={submitting}
                {...fieldProps('months_covered')}
              >
                {MONTH_OPTIONS.map((value) => (
                  <option key={value} value={value}>{value === 1 ? '1 mes' : `${value} meses`}</option>
                ))}
              </select>
              {fieldError('months_covered')}
            </label>

            <label>
              Monto ({subscription.currency})
              <input
                type="text"
                inputMode="decimal"
                value={amount}
                onChange={(event) => {
                  setAmountTouched(true);
                  setAmount(event.target.value);
                }}
                placeholder="0.00"
                disabled={submitting}
                {...fieldProps('amount')}
              />
              {fieldError('amount')}
            </label>
          </div>

          <label>
            Medio de pago
            <select
              value={method}
              onChange={(event) => setMethod(event.target.value as PaymentMethod | '')}
              disabled={submitting}
              {...fieldProps('method')}
            >
              <option value="">Elegí una opción</option>
              {(Object.keys(PAYMENT_METHOD_LABELS) as PaymentMethod[]).map((value) => (
                <option key={value} value={value}>{PAYMENT_METHOD_LABELS[value]}</option>
              ))}
            </select>
            {fieldError('method')}
          </label>

          <label>
            Nota (opcional)
            <textarea
              value={note}
              onChange={(event) => setNote(event.target.value)}
              rows={3}
              maxLength={NOTE_MAX}
              placeholder="Por ejemplo: transferencia desde la cuenta de un familiar."
              disabled={submitting}
              {...fieldProps('note')}
            />
            {fieldError('note')}
          </label>

          {isStudent && (
            <label>
              Comprobante (opcional)
              <input
                type="file"
                accept="application/pdf,image/jpeg,image/png"
                onChange={(event) => setReceipt(event.target.files?.[0] ?? null)}
                disabled={submitting}
                aria-invalid={Boolean(errors.receipt)}
                aria-describedby={errors.receipt ? 'payment-receipt-error' : 'payment-receipt-hint'}
              />
              {errors.receipt
                ? <small className="field-error" id="payment-receipt-error">{errors.receipt}</small>
                : <small className="payment-dialog__hint" id="payment-receipt-hint">PDF, JPG o PNG de hasta 10 MB. Solo lo ven vos y tu entrenador.</small>}
            </label>
          )}
          {isStudent && (
            <p className="payment-dialog__notice">
              Tu entrenador va a revisar el pago. Hasta que lo confirme, queda "Pendiente de confirmación" y no cambia tu vencimiento.
            </p>
          )}

          {formError && <p className="form-alert" role="alert">{formError}</p>}

          <div className="payment-dialog__actions">
            <button type="submit" className="profile-save" disabled={submitting}>
              {submitting ? 'Enviando…' : isStudent ? 'Informar pago' : replaces ? 'Registrar pago corregido' : 'Registrar pago'}
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
