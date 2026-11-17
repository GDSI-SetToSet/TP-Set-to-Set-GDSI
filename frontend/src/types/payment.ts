/** US-34: pagos informales y estado de suscripciones (vista del entrenador). */

export type SubscriptionStatus = 'AL_DIA' | 'POR_VENCER' | 'VENCIDA';
export type PaymentMethod = 'EFECTIVO' | 'TRANSFERENCIA' | 'OTRO';
export type PaymentStatus = 'PENDIENTE_CONFIRMACION' | 'CONFIRMADO' | 'RECHAZADO' | 'ANULADO';

export interface SubscriptionSummary {
  relationship_id: string;
  student_id: string;
  student_name: string;
  plan_id: string;
  plan_title: string;
  /** Decimal serializado como texto, p. ej. "25000.00". */
  agreed_monthly_price: string;
  currency: string;
  start_date: string;
  months_paid: number;
  due_date: string;
  /** Negativo si la suscripción está vencida. */
  days_until_due: number;
  status: SubscriptionStatus;
  last_payment_on: string | null;
  /** US-71 */
  trainer_id: string;
  trainer_name: string;
  pending_payment_count: number;
}

export interface PaymentView {
  id: string;
  paid_on: string;
  amount: string;
  currency: string;
  method: PaymentMethod;
  months_covered: number;
  status: PaymentStatus;
  note: string | null;
  registered_by_name: string;
  created_at: string;
  voided_at: string | null;
  voided_by_name: string | null;
  void_reason: string | null;
  replaces_payment_id: string | null;
  replaced_by_payment_id: string | null;
  /** US-71: origen, confirmación o rechazo y comprobante. */
  source: 'TRAINER' | 'STUDENT';
  confirmed_by_name: string | null;
  confirmed_at: string | null;
  rejected_by_name: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  has_receipt: boolean;
  receipt_filename: string | null;
}

export interface PaymentHistory {
  subscription: SubscriptionSummary;
  payments: PaymentView[];
}

export interface PaymentMutationResult {
  subscription: SubscriptionSummary;
  payment: PaymentView;
}

export interface PaymentCreatePayload {
  paid_on: string;
  amount: string;
  method: PaymentMethod;
  months_covered: number;
  note?: string | null;
  replaces_payment_id?: string | null;
}
