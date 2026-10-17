import { useCallback, useEffect, useState } from 'react';
import { LOGIN_LOCKOUT_STORAGE_PREFIX } from '../constants/auth';

interface StoredLockout {
  email: string;
  expiresAt: number;
}

function normalizedEmail(email: string): string {
  return email.trim().toLowerCase();
}

function storageKey(email: string): string {
  return `${LOGIN_LOCKOUT_STORAGE_PREFIX}${normalizedEmail(email)}`;
}

function readLockout(email: string): StoredLockout | null {
  const normalized = normalizedEmail(email);
  if (!normalized) return null;

  const expiresAt = Number(localStorage.getItem(storageKey(normalized)));
  if (!Number.isFinite(expiresAt) || expiresAt <= Date.now()) {
    localStorage.removeItem(storageKey(normalized));
    return null;
  }

  return { email: normalized, expiresAt };
}

export function useLoginLockout(email: string) {
  const [lockout, setLockout] = useState<StoredLockout | null>(() => readLockout(email));
  const [now, setNow] = useState(() => Date.now());
  const currentEmail = normalizedEmail(email);
  const expiresAt = lockout?.email === currentEmail ? lockout.expiresAt : null;

  useEffect(() => {
    setLockout(readLockout(email));
  }, [email]);

  useEffect(() => {
    if (expiresAt === null) return undefined;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [expiresAt]);

  useEffect(() => {
    if (expiresAt === null || expiresAt > now) return;
    localStorage.removeItem(storageKey(currentEmail));
    setLockout(null);
  }, [currentEmail, expiresAt, now]);

  const startLockout = useCallback((durationSeconds: number) => {
    const normalized = normalizedEmail(email);
    if (!normalized || durationSeconds <= 0) return;

    const nextExpiresAt = Date.now() + durationSeconds * 1000;
    localStorage.setItem(storageKey(normalized), String(nextExpiresAt));
    setLockout({ email: normalized, expiresAt: nextExpiresAt });
    setNow(Date.now());
  }, [email]);

  const remainingSeconds = expiresAt === null ? 0 : Math.max(0, Math.ceil((expiresAt - now) / 1000));

  return { remainingSeconds, startLockout };
}
