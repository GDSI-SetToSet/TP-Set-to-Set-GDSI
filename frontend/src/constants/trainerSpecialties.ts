export const TRAINER_SPECIALTIES = [
  'Fuerza',
  'Hipertrofia',
  'Resistencia',
  'Pérdida de peso',
  'Salud general',
  'Movilidad/rehabilitación',
] as const;

export function parseTrainerSpecialties(value: string | null | undefined): string[] {
  const parsed = value?.split(/\s*(?:\||,|;)\s*/).map((item) => item.trim()).filter(Boolean) ?? [];
  return [...new Set(parsed)];
}

export type TrainerSpecialty = (typeof TRAINER_SPECIALTIES)[number];
