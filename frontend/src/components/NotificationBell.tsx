import { useEffect, useRef, useState } from 'react';
import { Bell, Check, Sparkles } from 'lucide-react';
import { getNotifications, markNotificationAsRead } from '../services/discoveryService';
import type { NotificationItem } from '../types/discovery';

interface NotificationBellProps {
  onNotificationClick?: (notification: NotificationItem) => void;
}

export function NotificationBell({ onNotificationClick }: NotificationBellProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  async function loadNotifications() {
    setLoading(true);
    try {
      const data = await getNotifications();
      setNotifications(data.items);
      setUnreadCount(data.unread_count);
    } catch {
      // Ignore background load failures
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadNotifications();
    const interval = setInterval(loadNotifications, 30000);
    return () => clearInterval(interval);
  }, []);

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

  async function handleItemClick(notif: NotificationItem) {
    if (!notif.is_read) {
      try {
        const updated = await markNotificationAsRead(notif.id);
        setNotifications((prev) =>
          prev.map((item) => (item.id === notif.id ? updated : item)),
        );
        setUnreadCount((prev) => Math.max(0, prev - 1));
      } catch {
        // Fallback
      }
    }
    if (onNotificationClick) {
      onNotificationClick(notif);
    }
  }

  return (
    <div className="notification-bell-container" ref={containerRef}>
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
              notifications.map((notif) => (
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
                    <time className="notification-item__time">
                      {new Date(notif.created_at).toLocaleDateString('es-AR', {
                        day: '2-digit',
                        month: 'short',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </time>
                  </div>
                  {!notif.is_read && <span className="notification-item__dot" aria-label="No leída" />}
                </article>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
