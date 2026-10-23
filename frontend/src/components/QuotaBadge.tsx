interface QuotaBadgeProps {
  availableSlots: number;
  hasAvailableQuota: boolean;
}

export function QuotaBadge({ availableSlots, hasAvailableQuota }: QuotaBadgeProps) {
  if (!hasAvailableQuota) return <span className="quota-badge quota-badge--full">Sin cupos disponibles</span>;
  return (
    <span className="quota-badge quota-badge--open">
      {availableSlots === 1 ? '1 cupo disponible' : `${availableSlots} cupos disponibles`}
    </span>
  );
}
