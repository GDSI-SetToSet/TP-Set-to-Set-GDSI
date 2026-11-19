import type { PaymentMethod, SubscriptionStatus, SubscriptionSummary } from '../types/payment';

export const PAYMENT_METHOD_LABELS: Record<PaymentMethod, string> = {
  EFECTIVO: 'Efectivo',
  TRANSFERENCIA: 'Transferencia',
  OTRO: 'Otro',
};

export const SUBSCRIPTION_STATUS_LABELS: Record<SubscriptionStatus, string> = {
  AL_DIA: 'Al día',
  POR_VENCER: 'Por vencer',
  VENCIDA: 'Vencida',
};

/** "2026-11-01" → "01/11/2026", sin pasar por Date para no correr el día por la zona horaria. */
export function formatIsoDate(value: string | null | undefined): string {
  if (!value) return '—';
  const [year, month, day] = value.slice(0, 10).split('-');
  return `${day}/${month}/${year}`;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  // El backend guarda UTC sin zona; se agrega "Z" si falta para mostrar la hora local.
  const normalized = /[zZ]|[+-]\d{2}:\d{2}$/.test(value) ? value : `${value}Z`;
  return new Date(normalized).toLocaleString('es-AR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatMoney(amount: string | number, currency: string): string {
  const value = typeof amount === 'number' ? amount : Number(amount);
  try {
    return new Intl.NumberFormat('es-AR', { style: 'currency', currency, minimumFractionDigits: 2 }).format(value);
  } catch {
    return `${currency} ${value.toFixed(2)}`;
  }
}

/** Texto del estado que no depende del color (Principio I). */
export function dueDescription(subscription: Pick<SubscriptionSummary, 'status' | 'days_until_due'>): string {
  const days = subscription.days_until_due;
  if (subscription.status === 'VENCIDA') {
    const overdue = Math.abs(days);
    return overdue === 1 ? 'Vencida hace 1 día' : `Vencida hace ${overdue} días`;
  }
  if (days === 0) return 'Vence hoy';
  return days === 1 ? 'Vence mañana' : `Vence en ${days} días`;
}

export function suggestedAmount(monthlyPrice: string, months: number): string {
  const price = Number(monthlyPrice);
  if (!Number.isFinite(price) || months < 1) return '';
  return (price * months).toFixed(2);
}
