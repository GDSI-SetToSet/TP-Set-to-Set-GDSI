import { api } from './api';
import type { SafeVariant, SafeVariantInput, SafeVariantResolution } from '../types/safeVariant';

const trainerPath = (exerciseId: string) => `/api/v1/exercises/${exerciseId}/safe-variants`;

export async function getSafeVariants(exerciseId: string): Promise<SafeVariant[]> {
  const { data } = await api.get<SafeVariant[]>(trainerPath(exerciseId));
  return data;
}

export async function addSafeVariant(exerciseId: string, payload: SafeVariantInput): Promise<SafeVariant> {
  const { data } = await api.post<SafeVariant>(trainerPath(exerciseId), payload);
  return data;
}

export async function removeSafeVariant(exerciseId: string, variantId: string): Promise<void> {
  await api.delete(`${trainerPath(exerciseId)}/${variantId}`);
}

export async function resolveSafeVariant(exerciseId: string): Promise<SafeVariantResolution> {
  const { data } = await api.get<SafeVariantResolution>(`/api/v1/students/me/exercises/${exerciseId}/safe-variant`);
  return data;
}
