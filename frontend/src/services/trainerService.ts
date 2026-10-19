import { api } from './api';
import type { TrainerProfile, TrainerProfileUpdate } from '../types/trainer';

const PROFILE_PATH = '/api/v1/trainers/me/profile';

export async function getOwnTrainerProfile(): Promise<TrainerProfile> {
  const { data } = await api.get<TrainerProfile>(PROFILE_PATH);
  return data;
}

export async function updateOwnTrainerProfile(payload: TrainerProfileUpdate): Promise<TrainerProfile> {
  const { data } = await api.put<TrainerProfile>(PROFILE_PATH, payload);
  return data;
}

export async function getPublishedTrainerProfile(profileId: string): Promise<TrainerProfile> {
  const { data } = await api.get<TrainerProfile>(`/api/v1/trainers/${profileId}/profile`);
  return data;
}
