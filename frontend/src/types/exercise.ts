export const EXERCISE_CATEGORIES = {
  FUERZA: 'Fuerza',
  CARDIO: 'Cardio',
  MOVILIDAD: 'Movilidad',
  FLEXIBILIDAD: 'Flexibilidad',
  EQUILIBRIO: 'Equilibrio',
} as const;

export type ExerciseCategory = keyof typeof EXERCISE_CATEGORIES;
export type VideoPlatform = 'YOUTUBE' | 'VIMEO' | 'GOOGLE_DRIVE' | 'NONE';

export interface ExerciseInput {
  name: string;
  description: string;
  category: ExerciseCategory;
  target_muscle_group: string;
  equipment_needed: string;
  has_no_materials_alternative: boolean;
  video_url: string | null;
}

export interface Exercise extends ExerciseInput {
  id: string;
  trainer_id: string;
  video_platform: VideoPlatform;
  created_at: string;
  updated_at: string;
}
