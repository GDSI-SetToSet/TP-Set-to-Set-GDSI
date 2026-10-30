import { api } from './api';
import type { Exercise, ExerciseInput } from '../types/exercise';

const EXERCISES_PATH = '/api/v1/exercises';

export async function getExercises(muscleGroup?: string): Promise<Exercise[]> {
  const { data } = await api.get<Exercise[]>(EXERCISES_PATH, { params: muscleGroup ? { muscle_group: muscleGroup } : undefined });
  return data;
}

export async function createExercise(payload: ExerciseInput): Promise<Exercise> {
  const { data } = await api.post<Exercise>(EXERCISES_PATH, payload);
  return data;
}

export async function updateExercise(exerciseId: string, payload: ExerciseInput): Promise<Exercise> {
  const { data } = await api.put<Exercise>(`${EXERCISES_PATH}/${exerciseId}`, payload);
  return data;
}

export async function deleteExercise(exerciseId: string): Promise<void> {
  await api.delete(`${EXERCISES_PATH}/${exerciseId}`);
}
