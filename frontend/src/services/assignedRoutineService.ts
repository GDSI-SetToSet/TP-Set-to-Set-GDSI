import { api } from './api';
import type {
  ActiveStudent,
  AssignedRoutine,
  GenerateAIRoutineInput,
} from '../types/assignedRoutine';

export async function getActiveStudents(): Promise<ActiveStudent[]> {
  const { data } = await api.get<ActiveStudent[]>('/api/v1/trainers/me/active-students');
  return data;
}

export async function generateAIRoutine(
  payload: GenerateAIRoutineInput
): Promise<AssignedRoutine> {
  const { data } = await api.post<AssignedRoutine>('/api/v1/routines/generate-ai', payload);
  return data;
}

export async function getAssignedRoutine(routineId: string): Promise<AssignedRoutine> {
  const { data } = await api.get<AssignedRoutine>(`/api/v1/routines/assigned/${routineId}`);
  return data;
}

export async function approveAssignedRoutine(routineId: string): Promise<AssignedRoutine> {
  const { data } = await api.post<AssignedRoutine>(`/api/v1/routines/assigned/${routineId}/approve`);
  return data;
}

export async function getStudentAssignedRoutine(): Promise<AssignedRoutine | null> {
  const { data } = await api.get<AssignedRoutine | null>('/api/v1/students/me/assigned-routine');
  return data;
}
