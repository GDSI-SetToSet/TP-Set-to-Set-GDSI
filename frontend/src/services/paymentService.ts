import axios from 'axios';
import { api } from './api';
import { localDateInputValue } from '../utils/dailyRoutineFormat.mjs';
import type {
  PaymentCreatePayload,
  PaymentHistory,
  PaymentMutationResult,
  SubscriptionStatus,
  SubscriptionSummary,
} from '../types/payment';

/** US-34: el estado de la suscripción se calcula con la fecha local del entrenador ("hoy"). */
function todayParams(extra: Record<string, string> = {}) {
  return { date: localDateInputValue(), ...extra };
}

export async function listSubscriptions(status?: SubscriptionStatus): Promise<SubscriptionSummary[]> {
  const { data } = await api.get<SubscriptionSummary[]>('/api/v1/trainers/me/subscriptions', {
    params: todayParams(status ? { status } : {}),
  });
  return data;
}

export async function getPaymentHistory(studentId: string): Promise<PaymentHistory> {
  const { data } = await api.get<PaymentHistory>(
    `/api/v1/trainers/me/students/${encodeURIComponent(studentId)}/payments`,
    { params: todayParams() },
  );
  return data;
}

export async function registerPayment(
  studentId: string,
  payload: PaymentCreatePayload,
): Promise<PaymentMutationResult> {
  const { data } = await api.post<PaymentMutationResult>(
    `/api/v1/trainers/me/students/${encodeURIComponent(studentId)}/payments`,
    payload,
    { params: todayParams() },
  );
  return data;
}

export async function voidPayment(paymentId: string, reason: string): Promise<PaymentMutationResult> {
  const { data } = await api.post<PaymentMutationResult>(
    `/api/v1/trainers/me/payments/${encodeURIComponent(paymentId)}/void`,
    { reason },
    { params: todayParams() },
  );
  return data;
}

/** Errores por campo de una respuesta RFC 7807 (`errors[]`), indexados por nombre de campo. */
export function getFieldErrors(error: unknown): Record<string, string> {
  if (!axios.isAxiosError(error)) return {};
  const errors = (error.response?.data as { errors?: { field: string; message: string }[] } | undefined)?.errors;
  if (!Array.isArray(errors)) return {};
  return Object.fromEntries(errors.map((item) => [item.field, item.message]));
}

/** US-71: suscripciones del alumno autenticado (una por vínculo activo). */
export async function listStudentSubscriptions(): Promise<SubscriptionSummary[]> {
  const { data } = await api.get<SubscriptionSummary[]>('/api/v1/students/me/subscriptions', { params: todayParams() });
  return data;
}

export async function getStudentPaymentHistory(relationshipId: string): Promise<PaymentHistory> {
  const { data } = await api.get<PaymentHistory>(
    `/api/v1/students/me/subscriptions/${encodeURIComponent(relationshipId)}/payments`,
    { params: todayParams() },
  );
  return data;
}

/** US-71: el alumno informa un pago (multipart, con comprobante opcional). */
export async function reportPayment(
  relationshipId: string,
  payload: PaymentCreatePayload,
  receipt: File | null,
): Promise<PaymentMutationResult> {
  const form = new FormData();
  form.append('paid_on', payload.paid_on);
  form.append('amount', payload.amount);
  form.append('method', payload.method);
  form.append('months_covered', String(payload.months_covered));
  if (payload.note) form.append('note', payload.note);
  if (receipt) form.append('receipt', receipt);
  const { data } = await api.post<PaymentMutationResult>(
    `/api/v1/students/me/subscriptions/${encodeURIComponent(relationshipId)}/payments`,
    form,
    { params: todayParams(), headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return data;
}

export async function confirmPayment(paymentId: string): Promise<PaymentMutationResult> {
  const { data } = await api.post<PaymentMutationResult>(
    `/api/v1/trainers/me/payments/${encodeURIComponent(paymentId)}/confirm`,
    null,
    { params: todayParams() },
  );
  return data;
}

export async function rejectPayment(paymentId: string, reason: string): Promise<PaymentMutationResult> {
  const { data } = await api.post<PaymentMutationResult>(
    `/api/v1/trainers/me/payments/${encodeURIComponent(paymentId)}/reject`,
    { reason },
    { params: todayParams() },
  );
  return data;
}

/** Descarga autenticada del comprobante (el token viaja en el header, no en la URL). */
export async function downloadReceipt(paymentId: string, filename: string | null): Promise<void> {
  const { data } = await api.get<Blob>(`/api/v1/payments/${encodeURIComponent(paymentId)}/receipt`, {
    responseType: 'blob',
  });
  const url = URL.createObjectURL(data);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename || 'comprobante';
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
