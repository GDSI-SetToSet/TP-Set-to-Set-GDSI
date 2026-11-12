import { api } from './api';
import type { AbandonmentRiskItem, TrainerStudentDetail, TrainerStudentListItem } from '../types/trainerStudent';

const STUDENTS_PATH = '/api/v1/trainers/me/students';

export async function getTrainerStudents(): Promise<TrainerStudentListItem[]> {
  const { data } = await api.get<TrainerStudentListItem[]>(STUDENTS_PATH);
  return data;
}

export async function getTrainerStudentDetail(studentId: string): Promise<TrainerStudentDetail> {
  const { data } = await api.get<TrainerStudentDetail>(`${STUDENTS_PATH}/${studentId}`);
  return data;
}

/** US-32: riesgo de abandono de los alumnos activos (en riesgo primero). */
export async function getAbandonmentRisk(): Promise<AbandonmentRiskItem[]> {
  const { data } = await api.get<AbandonmentRiskItem[]>('/api/v1/trainers/me/abandonment-risk');
  return data;
}
