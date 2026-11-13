import { api } from './api';
import type {
  AdjustmentInput,
  AdjustmentView,
  SessionAdjustmentContext,
  StudentAdjustmentNotice,
} from '../types/sessionAdjustment';

const adjustmentPath = (sessionId: string) => `/api/v1/trainers/me/sessions/${sessionId}/adjustment`;

export async function getSessionAdjustment(sessionId: string): Promise<SessionAdjustmentContext> {
  const { data } = await api.get<SessionAdjustmentContext>(adjustmentPath(sessionId));
  return data;
}

export async function saveSessionAdjustment(sessionId: string, payload: AdjustmentInput): Promise<AdjustmentView> {
  const { data } = await api.put<AdjustmentView>(adjustmentPath(sessionId), payload);
  return data;
}

/** Días con ejercicios "Ajustado por tu entrenador" que el alumno todavía no entrenó. */
export async function getStudentAdjustments(): Promise<StudentAdjustmentNotice[]> {
  const { data } = await api.get<StudentAdjustmentNotice[]>('/api/v1/students/me/routine-adjustments');
  return data;
}
