import { api } from './api';
import type {
  SafetyAlertReviewRequest,
  SafetyAlertStatus,
  SafetyAlertView,
  StudentPainAlertReviewedNotice,
} from '../types/safetyAlert';

export async function getTrainerSafetyAlerts(params?: {
  status?: SafetyAlertStatus;
  student_id?: string;
}): Promise<SafetyAlertView[]> {
  const { data } = await api.get<SafetyAlertView[]>('/api/v1/trainers/me/safety-alerts', {
    params,
  });
  return data;
}

export async function getTrainerStudentSafetyAlerts(
  studentId: string,
  params?: { status?: SafetyAlertStatus },
): Promise<SafetyAlertView[]> {
  const { data } = await api.get<SafetyAlertView[]>(
    `/api/v1/trainers/me/students/${studentId}/safety-alerts`,
    { params },
  );
  return data;
}

export async function reviewSafetyAlert(
  alertId: string,
  payload: SafetyAlertReviewRequest,
): Promise<SafetyAlertView> {
  const { data } = await api.patch<SafetyAlertView>(
    `/api/v1/trainers/me/safety-alerts/${alertId}/review`,
    payload,
  );
  return data;
}

export async function getStudentReviewedPainNotices(): Promise<StudentPainAlertReviewedNotice[]> {
  const { data } = await api.get<StudentPainAlertReviewedNotice[]>(
    '/api/v1/students/me/safety-alerts/reviewed-notices',
  );
  return data;
}

export async function markSafetyAlertSeen(
  alertId: string,
): Promise<StudentPainAlertReviewedNotice> {
  const { data } = await api.post<StudentPainAlertReviewedNotice>(
    `/api/v1/students/me/safety-alerts/${alertId}/seen`,
  );
  return data;
}
