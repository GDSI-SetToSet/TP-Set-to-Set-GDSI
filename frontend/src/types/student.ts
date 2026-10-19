export type StudentProfileStatus = 'DRAFT' | 'PUBLISHED';

export interface StudentProfile {
  id: string;
  user_id: string;
  full_name: string | null;
  birth_date: string | null;
  contact_phone: string | null;
  profile_picture: string | null;
  bio: string | null;
  status: StudentProfileStatus;
  created_at: string;
  updated_at: string;
}

export type StudentProfileUpdate = Partial<Pick<
  StudentProfile,
  'full_name' | 'birth_date' | 'contact_phone' | 'profile_picture' | 'bio'
>>;