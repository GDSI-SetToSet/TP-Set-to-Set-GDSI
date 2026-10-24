import axios from 'axios';
import { api } from './api';
import type {
  PaginatedTrainers,
  StudentGoalsSummary,
  TrainerPublicDetail,
  TrainerSearchFilters,
  TrainingRelationshipResponse,
  TrainingRequestAcceptPayload,
  TrainingRequestCreate,
  TrainingRequestDetailResponse,
  TrainingRequestRejectPayload,
  TrainingRequestResponse,
  TrainingRequestStatus,
} from '../types/discovery';
import type { HealthQuestionnaire } from '../types/student';

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

export async function getTrainerRequests(
  status?: TrainingRequestStatus,
): Promise<TrainingRequestResponse[]> {
  const { data } = await api.get<TrainingRequestResponse[]>('/api/v1/matchmaking/requests', {
    params: status ? { status } : undefined,
  });
  return data;
}

export async function getTrainerRequestDetail(
  requestId: string,
): Promise<TrainingRequestDetailResponse> {
  const { data } = await api.get<TrainingRequestDetailResponse>(
    `/api/v1/matchmaking/requests/${requestId}`,
  );
  return data;
}

export async function acceptTrainingRequest(
  requestId: string,
  payload?: TrainingRequestAcceptPayload,
): Promise<TrainingRelationshipResponse> {
  const { data } = await api.post<TrainingRelationshipResponse>(
    `/api/v1/matchmaking/requests/${requestId}/accept`,
    payload ?? {},
  );
  return data;
}

export async function rejectTrainingRequest(
  requestId: string,
  payload?: TrainingRequestRejectPayload,
): Promise<TrainingRequestResponse> {
  const { data } = await api.post<TrainingRequestResponse>(
    `/api/v1/matchmaking/requests/${requestId}/reject`,
    payload ?? {},
  );
  return data;
}

export async function getStudentGoalsForTrainer(studentId: string): Promise<StudentGoalsSummary> {
  const { data } = await api.get<StudentGoalsSummary>(`/api/v1/students/${studentId}/goals`);
  return data;
}

export async function getStudentHealthForTrainer(
  studentId: string,
): Promise<HealthQuestionnaire | null> {
  try {
    const { data } = await api.get<HealthQuestionnaire>(
      `/api/v1/students/${studentId}/health-questionnaire`,
    );
    return data;
  } catch (caught) {
    if (axios.isAxiosError(caught) && caught.response?.status === 404) return null;
    throw caught;
  }
}
