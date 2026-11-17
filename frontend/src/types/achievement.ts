/** US-67: logros y medallas del alumno. */

export interface Congratulation {
  message: string;
  trainer_name: string;
  created_at: string;
  seen_at: string | null;
}

export interface AchievementItem {
  id: string;
  code: string;
  title: string;
  description: string;
  unlocked_at: string;
  retroactive: boolean;
  pending_celebration: boolean;
  congratulation: Congratulation | null;
}

export interface LockedAchievement {
  code: string;
  title: string;
  description: string;
  current: number;
  target: number;
}

export interface AchievementsOverview {
  unlocked: AchievementItem[];
  locked: LockedAchievement[];
}
