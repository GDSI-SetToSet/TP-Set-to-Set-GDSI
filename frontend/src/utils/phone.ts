// Mismo patrón que PHONE_PATTERN del backend: '+' opcional y solo dígitos.
export function phoneError(value: string, minDigits: number, maxDigits = 15): string {
  const phone = value.trim();
  if (!phone) return '';
  const valid = new RegExp(`^\\+?[0-9]{${minDigits},${maxDigits}}$`).test(phone);
  return valid ? '' : `El teléfono debe tener entre ${minDigits} y ${maxDigits} dígitos, con '+' inicial opcional.`;
}
