import { api } from './api';
import type { ProgressFilters, StudentProgress, TrainingStreak } from '../types/studentProgress';

/** US-65: evolución del alumno autenticado (progreso por ejercicio, constancia, récords y próxima sesión). */
export async function getStudentProgress(filters: ProgressFilters): Promise<StudentProgress> {
  const { data } = await api.get<StudentProgress>('/api/v1/students/me/progress', {
    params: { period: filters.period, muscle_group: filters.muscle_group || undefined },
  });
  return data;
}

/** US-68: racha del alumno autenticado (si la última semana cortó la racha, el backend envía el mensaje de aliento). */
export async function getStudentStreak(): Promise<TrainingStreak> {
  const { data } = await api.get<TrainingStreak>('/api/v1/students/me/streak');
  return data;
}
