export type StudentProfileStatus = 'DRAFT' | 'PUBLISHED';

export const FITNESS_GOALS = {
  fuerza: 'Fuerza',
  hipertrofia: 'Hipertrofia',
  resistencia: 'Resistencia',
  perdida_de_peso: 'Pérdida de peso',
  salud_general: 'Salud general',
  movilidad_rehabilitacion: 'Movilidad/rehabilitación',
} as const;

export type FitnessGoal = keyof typeof FITNESS_GOALS;

export interface StudentProfile {
  id: string;
  user_id: string;
  first_name: string | null;
  last_name: string | null;
  birth_date: string | null;
  contact_phone: string | null;
  profile_picture: string | null;
  bio: string | null;
  fitness_goals: FitnessGoal[];
  personal_motivation: string | null;
  status: StudentProfileStatus;
  created_at: string;
  updated_at: string;
}

export type StudentProfileUpdate = Partial<Pick<
  StudentProfile,
  'first_name' | 'last_name' | 'birth_date' | 'contact_phone' | 'profile_picture' | 'bio' | 'fitness_goals' | 'personal_motivation'
>>;