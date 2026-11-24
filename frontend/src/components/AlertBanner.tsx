import React from 'react';
import { AlertTriangle, AlertCircle, Info, CheckCircle2 } from 'lucide-react';

interface AlertBannerProps {
  type: 'warning' | 'error' | 'info' | 'success';
  title?: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
}

export const AlertBanner: React.FC<AlertBannerProps> = ({
  type,
  title,
  message,
  actionLabel,
  onAction,
}) => {
  const styles = {
    warning: {
      bg: 'bg-amber-50 border-amber-300 text-amber-900',
      icon: <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0" />,
      btn: 'bg-amber-600 hover:bg-amber-700 text-white',
    },
    error: {
      bg: 'bg-rose-50 border-rose-300 text-rose-900',
      icon: <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0" />,
      btn: 'bg-rose-600 hover:bg-rose-700 text-white',
    },
    info: {
      bg: 'bg-sky-50 border-sky-300 text-sky-900',
      icon: <Info className="w-5 h-5 text-sky-600 flex-shrink-0" />,
      btn: 'bg-sky-600 hover:bg-sky-700 text-white',
    },
    success: {
      bg: 'bg-emerald-50 border-emerald-300 text-emerald-900',
      icon: <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />,
      btn: 'bg-emerald-600 hover:bg-emerald-700 text-white',
    },
  }[type];

  return (
    <div className={`p-3.5 rounded-lg border shadow-sm flex items-start space-x-3 ${styles.bg}`}>
      {styles.icon}
      <div className="flex-1 text-sm">
        {title && <h4 className="font-semibold mb-0.5">{title}</h4>}
        <p className="text-xs sm:text-sm leading-relaxed">{message}</p>
        {actionLabel && onAction && (
          <button
            type="button"
            onClick={onAction}
            className={`mt-2 px-3 py-1 text-xs font-medium rounded transition-colors ${styles.btn}`}
          >
            {actionLabel}
          </button>
        )}
      </div>
    </div>
  );
};

