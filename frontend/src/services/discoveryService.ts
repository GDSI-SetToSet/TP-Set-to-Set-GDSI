import { api } from './api';
import type {
  PaginatedTrainers,
  TrainerPublicDetail,
  TrainerSearchFilters,
  TrainingRequestCreate,
  TrainingRequestResponse,
} from '../types/discovery';

export async function searchTrainers(filters: TrainerSearchFilters = {}): Promise<PaginatedTrainers> {
  const { data } = await api.get<PaginatedTrainers>('/api/v1/trainers/search', { params: filters });
  return data;
}

export async function getTrainerPublicDetail(trainerId: string): Promise<TrainerPublicDetail> {
  const { data } = await api.get<TrainerPublicDetail>(`/api/v1/trainers/${trainerId}/public`);
  return data;
}

export async function sendTrainingRequest(payload: TrainingRequestCreate): Promise<TrainingRequestResponse> {
  const { data } = await api.post<TrainingRequestResponse>('/api/v1/matchmaking/requests', payload);
  return data;
}

export async function getMyRequests(): Promise<TrainingRequestResponse[]> {
  const { data } = await api.get<TrainingRequestResponse[]>('/api/v1/matchmaking/requests/mine');
  return data;
}
