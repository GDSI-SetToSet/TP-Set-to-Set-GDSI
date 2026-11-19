import { api } from './api';
import type { AchievementItem, AchievementsOverview } from '../types/achievement';

/** US-67: logros del alumno autenticado (el servidor evalúa los pendientes, p. ej. la racha). */
export async function getStudentAchievements(): Promise<AchievementsOverview> {
  const { data } = await api.get<AchievementsOverview>('/api/v1/students/me/achievements');
  return data;
}

export async function markAchievementCelebrated(achievementId: string): Promise<void> {
  await api.post(`/api/v1/students/me/achievements/${encodeURIComponent(achievementId)}/celebrated`);
}

export async function markCongratulationSeen(achievementId: string): Promise<void> {
  await api.post(`/api/v1/students/me/achievements/${encodeURIComponent(achievementId)}/congratulation/seen`);
}

export async function getTrainerStudentAchievements(studentId: string): Promise<AchievementsOverview> {
  const { data } = await api.get<AchievementsOverview>(
    `/api/v1/trainers/me/students/${encodeURIComponent(studentId)}/achievements`,
  );
  return data;
}

export async function congratulateAchievement(achievementId: string, message: string): Promise<AchievementItem> {
  const { data } = await api.post<AchievementItem>(
    `/api/v1/trainers/me/achievements/${encodeURIComponent(achievementId)}/congratulation`,
    { message },
  );
  return data;
}
