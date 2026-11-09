import { api } from './api';
import type { AlternativesResponse, ReplacementInput } from '../types/exerciseAlternative';

export async function getAlternatives(exerciseId: string): Promise<AlternativesResponse> {
  const { data } = await api.get<AlternativesResponse>(`/api/v1/students/me/exercises/${exerciseId}/alternatives`);
  return data;
}

export async function saveReplacement(payload: ReplacementInput): Promise<void> {
  await api.put('/api/v1/students/me/exercise-replacements', payload);
}
