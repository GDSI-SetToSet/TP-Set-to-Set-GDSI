import { api } from './api';
import type { AbandonmentRiskItem, DailyRoutineItem, TrainerStudentDetail, TrainerStudentListItem } from '../types/trainerStudent';

const STUDENTS_PATH = '/api/v1/trainers/me/students';

export async function getTrainerStudents(): Promise<TrainerStudentListItem[]> {
  const { data } = await api.get<TrainerStudentListItem[]>(STUDENTS_PATH);
  return data;
}

export async function getTrainerStudentDetail(studentId: string): Promise<TrainerStudentDetail> {
  const { data } = await api.get<TrainerStudentDetail>(`${STUDENTS_PATH}/${studentId}`);
  return data;
}

/** US-22: rutinas del día de los alumnos activos, en el día local del entrenador. */
export async function getTrainerDailyRoutines(date: string): Promise<DailyRoutineItem[]> {
  const { data } = await api.get<DailyRoutineItem[]>('/api/v1/trainers/me/daily-routines', {
    params: { date, utc_offset_minutes: -new Date(`${date}T12:00:00`).getTimezoneOffset() },
  });
  return data;
}

/** US-32: riesgo de abandono de los alumnos activos (en riesgo primero). */
export async function getAbandonmentRisk(): Promise<AbandonmentRiskItem[]> {
  const { data } = await api.get<AbandonmentRiskItem[]>('/api/v1/trainers/me/abandonment-risk');
  return data;
}
