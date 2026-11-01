import { api } from './api';
import type { RoutineDraftInput, StudentRoutineView } from '../types/studentRoutine';

const path = (studentId: string) => `/api/v1/trainers/me/students/${studentId}/routine`;

export async function getStudentRoutine(studentId: string): Promise<StudentRoutineView> {
  const { data } = await api.get<StudentRoutineView>(path(studentId));
  return data;
}

export async function saveRoutineDraft(studentId: string, payload: RoutineDraftInput): Promise<number> {
  const { data } = await api.put<{ draft_version: number }>(`${path(studentId)}/draft`, payload);
  return data.draft_version;
}

export async function discardRoutineDraft(studentId: string): Promise<void> {
  await api.delete(`${path(studentId)}/draft`);
}

export async function confirmRoutineDraft(studentId: string): Promise<StudentRoutineView> {
  const { data } = await api.post<StudentRoutineView>(`${path(studentId)}/draft/confirm`);
  return data;
}
