import { api } from './api';
import type { ProgressFilters, StudentProgress } from '../types/studentProgress';

/** US-65: evolución de cargas, volumen semanal y PRs del alumno autenticado. */
export async function getStudentProgress(filters: ProgressFilters = {}): Promise<StudentProgress> {
  const params = Object.fromEntries(Object.entries(filters).filter(([, value]) => value));
  const { data } = await api.get<StudentProgress>('/api/v1/students/me/progress', { params });
  return data;
}
