import { api } from './api';
import type { TrainerProfile, TrainerProfileUpdate, TrainingPlan, TrainingPlanInput } from '../types/trainer';

const PROFILE_PATH = '/api/v1/trainers/me/profile';
const PLANS_PATH = '/api/v1/trainers/me/plans';

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

export async function getOwnTrainingPlans(): Promise<TrainingPlan[]> {
  const { data } = await api.get<TrainingPlan[]>(PLANS_PATH);
  return data;
}

export async function createTrainingPlan(payload: TrainingPlanInput): Promise<TrainingPlan> {
  const { data } = await api.post<TrainingPlan>(PLANS_PATH, payload);
  return data;
}

export async function updateTrainingPlan(planId: string, payload: TrainingPlanInput): Promise<TrainingPlan> {
  const { data } = await api.put<TrainingPlan>(`${PLANS_PATH}/${planId}`, payload);
  return data;
}

export async function archiveTrainingPlan(planId: string): Promise<TrainingPlan> {
  const { data } = await api.post<TrainingPlan>(`${PLANS_PATH}/${planId}/archive`);
  return data;
}

export async function getPublishedTrainingPlans(profileId: string): Promise<TrainingPlan[]> {
  const { data } = await api.get<TrainingPlan[]>(`/api/v1/trainers/${profileId}/plans`);
  return data;
}
