import type { SafetyAlertView } from '../types/safetyAlert';
import type { AbandonmentRiskItem } from '../types/trainerStudent';

export function sortByAbandonmentRisk<T extends { relationship_id: string }>(
  students: T[],
  risks: Pick<AbandonmentRiskItem, 'relationship_id' | 'at_risk' | 'days_without_report'>[],
  safetyAlerts?: SafetyAlertView[],
): T[];
export function abandonmentRiskDescription(risk: AbandonmentRiskItem | undefined): string;
