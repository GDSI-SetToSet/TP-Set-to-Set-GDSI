import { api } from './api';
import type { TrainerStudentDetail, TrainerStudentListItem } from '../types/trainerStudent';

const STUDENTS_PATH = '/api/v1/trainers/me/students';

export async function getTrainerStudents(): Promise<TrainerStudentListItem[]> {
  const { data } = await api.get<TrainerStudentListItem[]>(STUDENTS_PATH);
  return data;
}

export async function getTrainerStudentDetail(studentId: string): Promise<TrainerStudentDetail> {
  const { data } = await api.get<TrainerStudentDetail>(`${STUDENTS_PATH}/${studentId}`);
  return data;
}
