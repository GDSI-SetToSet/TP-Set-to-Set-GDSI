import type { RoutineAssignmentStudent } from '../types/routineTemplate';
import type { SafetyAlertView } from '../types/safetyAlert';
import type { TrainingPlan } from '../types/trainer';
import type { AbandonmentRiskItem } from '../types/trainerStudent';

export const LOAD_STUDENTS_ERROR: string;
export const LOAD_PLANS_ERROR: string;
export const LOAD_RISK_ERROR: string;
export const LOAD_SAFETY_ALERTS_ERROR: string;

export interface AssignmentAuxiliaryState {
  trainerPlans: TrainingPlan[];
  plansError: string;
  abandonmentRisks: AbandonmentRiskItem[];
  riskError: string;
  safetyAlerts: SafetyAlertView[];
  safetyAlertsError: string;
}

export interface AssignmentLoadResolution extends AssignmentAuxiliaryState {
  students: RoutineAssignmentStudent[] | null;
  error: string;
}

export function resolveAssignmentLoadResults(
  studentsResult: PromiseSettledResult<RoutineAssignmentStudent[]>,
  plansResult: PromiseSettledResult<TrainingPlan[]>,
  risksResult: PromiseSettledResult<AbandonmentRiskItem[]>,
  safetyAlertsResult?: PromiseSettledResult<SafetyAlertView[]>,
): AssignmentLoadResolution;

export function applyAuxiliaryRetry(
  currentState: AssignmentAuxiliaryState,
  plansResult: PromiseSettledResult<TrainingPlan[]> | null,
  risksResult: PromiseSettledResult<AbandonmentRiskItem[]> | null,
  safetyAlertsResult?: PromiseSettledResult<SafetyAlertView[]> | null,
): AssignmentAuxiliaryState;
