import { useCallback, useEffect, useRef, useState } from 'react';
import { Bell, Check, Sparkles } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { USER_ROLES } from '../constants/auth';
import { studentNotificationPath, trainerNotificationPath } from '../constants/routes';
import { useAuth } from '../context/AuthContext';
import { getNotifications, markNotificationAsRead } from '../services/discoveryService';
import type { NotificationItem } from '../types/discovery';
import { formatNotificationTime } from '../utils/notificationFormat.mjs';

interface NotificationBellProps {
  onNotificationClick?: (notification: NotificationItem) => void;
}

export function NotificationBell({ onNotificationClick }: NotificationBellProps) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [actionError, setActionError] = useState('');
  const containerRef = useRef<HTMLDivElement>(null);
  const requestSeqRef = useRef(0);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      requestSeqRef.current += 1;
    };
  }, []);

  const loadNotifications = useCallback(async () => {
    if (!user?.role) return;
    const seq = ++requestSeqRef.current;
    setLoading(true);
    try {
      const data = await getNotifications(undefined, undefined, undefined, user.role);
      if (!mountedRef.current || requestSeqRef.current !== seq) return;
      setNotifications(data.items);
      setUnreadCount(data.unread_count);
      setActionError('');
    } catch {
      if (!mountedRef.current || requestSeqRef.current !== seq) return;
      setActionError('No se pudieron cargar las notificaciones. Intentá nuevamente.');
    } finally {
      if (mountedRef.current && requestSeqRef.current === seq) {
        setLoading(false);
      }
    }
  }, [user?.role]);

  useEffect(() => {
    if (!user?.role) return undefined;
    void loadNotifications();
    const interval = setInterval(() => {
      if (document.visibilityState === 'visible') {
        void loadNotifications();
      }
    }, 30000);
    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        void loadNotifications();
      }
    };
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [loadNotifications, user?.role]);

  // Close on outside click or Escape
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setIsOpen(false);
    }
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  async function markAsRead(notif: NotificationItem): Promise<boolean> {
    if (!notif.is_read) {
      if (!user?.role) return false;
      requestSeqRef.current += 1;
      setActionError('');
      try {
        const updated = await markNotificationAsRead(notif.id, user.role);
        if (!mountedRef.current) return false;
        setNotifications((prev) =>
          prev.map((item) => (item.id === notif.id ? updated : item)),
        );
        setUnreadCount((prev) => Math.max(0, prev - 1));
        return true;
      } catch {
        setActionError('No se pudo marcar la notificación como leída. Intentá nuevamente.');
        return false;
      }
    }
    return true;
  }

  async function handleItemClick(notif: NotificationItem) {
    const marked = await markAsRead(notif);
    if (!marked) {
      return;
    }
    setIsOpen(false);
    if (onNotificationClick) {
      onNotificationClick(notif);
    } else if (user?.role === USER_ROLES.trainer) {
      navigate(trainerNotificationPath(notif));
    } else if (user?.role === USER_ROLES.student) {
      navigate(studentNotificationPath(notif));
    }
  }

  const displayedNotifications = [
    ...notifications.filter((notification) => !notification.is_read),
    ...notifications.filter((notification) => notification.is_read).slice(0, 5),
  ].sort(
    (first, second) =>
      new Date(second.created_at).getTime() - new Date(first.created_at).getTime(),
  );

  return (
    <div
      className={`notification-bell-container${user?.role === USER_ROLES.student ? ' notification-bell-container--student' : user?.role === USER_ROLES.trainer ? ' notification-bell-container--trainer' : ''}`}
      ref={containerRef}
    >
      <button
        type="button"
        className="notification-bell-btn"
        aria-label={`Notificaciones (${unreadCount} no leídas)`}
        aria-expanded={isOpen}
        onClick={() => setIsOpen((prev) => !prev)}
      >
        <Bell size={20} />
        {unreadCount > 0 && (
          <span className="notification-bell-badge" aria-hidden="true">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="notification-dropdown" role="region" aria-label="Centro de notificaciones">
          <header className="notification-dropdown__header">
            <h4>Notificaciones</h4>
            <span className="notification-dropdown__unread-label">
              {unreadCount} no leída{unreadCount !== 1 ? 's' : ''}
            </span>
          </header>

          <div className="notification-dropdown__list">
            {loading && notifications.length === 0 ? (
              <div className="notification-dropdown__empty">Cargando...</div>
            ) : notifications.length === 0 ? (
              <div className="notification-dropdown__empty">No tenés notificaciones aún.</div>
            ) : (
              displayedNotifications.map((notif) => (
                <article
                  key={notif.id}
                  className={`notification-item ${!notif.is_read ? 'notification-item--unread' : ''}`}
                  onClick={() => handleItemClick(notif)}
                  tabIndex={0}
                  role="button"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleItemClick(notif);
                    }
                  }}
                >
                  <div className="notification-item__icon">
                    {notif.type === 'TRAINING_ACCEPTED' ? (
                      <Sparkles size={16} className="text-accent" />
                    ) : (
                      <Check size={16} />
                    )}
                  </div>
                  <div className="notification-item__body">
                    <h5 className="notification-item__title">{notif.title}</h5>
                    <p className="notification-item__message">{notif.message}</p>
                    <time className="notification-item__time" dateTime={notif.created_at}>
                      {formatNotificationTime(notif.created_at)}
                    </time>
                  </div>
                  {!notif.is_read && <span className="notification-item__dot" aria-label="No leída" />}
                </article>
              ))
            )}
          </div>
          {actionError && (
            <div className="notification-dropdown__error" role="alert">
              {actionError}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
