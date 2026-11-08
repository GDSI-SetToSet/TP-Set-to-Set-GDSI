import type { VideoPlatform } from './exercise';

export interface SafeVariant {
  id: string;
  variant_exercise_id: string;
  variant_name: string;
  covered_zones: string[];
}

export interface SafeVariantInput {
  variant_exercise_id: string;
  covered_zones: string[];
}

export interface SafeVariantResolution {
  status: 'SAFE' | 'VARIANT' | 'BLOCKED';
  variant: {
    exercise_id: string;
    name: string;
    description: string;
    video_url: string | null;
    video_platform: VideoPlatform;
  } | null;
  message: string | null;
  can_skip: boolean;
}
