import { api } from './api';
import type {
  ActionTaken,
  BodyMapReportCreate,
  BodyMapReportResponse,
  BodyMapZoneHistoryItem,
} from '../types/bodyMapReport';

export async function createBodyMapReport(
  payload: BodyMapReportCreate
): Promise<BodyMapReportResponse> {
  const { data } = await api.post<BodyMapReportResponse>('/api/v1/body-map-reports', payload);
  return data;
}

export async function updateReportAction(
  reportId: string,
  actionTaken: ActionTaken
): Promise<BodyMapReportResponse> {
  const { data } = await api.patch<BodyMapReportResponse>(
    `/api/v1/body-map-reports/${reportId}/action`,
    { action_taken: actionTaken }
  );
  return data;
}

export async function getStudentBodyMapReports(params?: {
  zone?: string;
  intensity?: string;
  session_id?: string;
}): Promise<BodyMapReportResponse[]> {
  const { data } = await api.get<BodyMapReportResponse[]>('/api/v1/students/me/body-map-reports', {
    params,
  });
  return data;
}

export async function getStudentZoneHistory(params?: {
  zone?: string;
  intensity?: string;
}): Promise<BodyMapZoneHistoryItem[]> {
  const { data } = await api.get<BodyMapZoneHistoryItem[]>(
    '/api/v1/students/me/body-map-reports/by-zone',
    { params }
  );
  return data;
}

export async function getTrainerStudentBodyMapReports(
  studentId: string,
  params?: { zone?: string; intensity?: string; limit?: number; offset?: number }
): Promise<BodyMapReportResponse[]> {
  const { data } = await api.get<BodyMapReportResponse[]>(
    `/api/v1/trainers/me/students/${studentId}/body-map-reports`,
    { params }
  );
  return data;
}

export async function getAllTrainerStudentBodyMapReports(
  studentId: string,
): Promise<BodyMapReportResponse[]> {
  const reports: BodyMapReportResponse[] = [];
  const pageSize = 200;
  let offset = 0;

  while (true) {
    const page = await getTrainerStudentBodyMapReports(studentId, { limit: pageSize, offset });
    reports.push(...page);
    if (page.length < pageSize) return reports;
    offset += page.length;
  }
}

export async function getTrainerStudentZoneHistory(
  studentId: string,
  params?: { zone?: string; intensity?: string }
): Promise<BodyMapZoneHistoryItem[]> {
  const { data } = await api.get<BodyMapZoneHistoryItem[]>(
    `/api/v1/trainers/me/students/${studentId}/body-map-reports/by-zone`,
    { params }
  );
  return data;
}
