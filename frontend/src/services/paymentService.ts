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
