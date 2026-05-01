// Formatters for consistent number, currency, time, and duration display

export const formatCurrency = (value: number, decimals = 2): string => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
};

export const formatPrice = (value: number, decimals = 5): string => {
  return value.toFixed(decimals).padStart(8, ' ');
};

export const formatPercent = (value: number, decimals = 2): string => {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(decimals)}%`;
};

export const formatNumber = (value: number, decimals = 0): string => {
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
};

export const formatPnL = (value: number): string => {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${formatCurrency(value, 2)}`;
};

export const formatSpread = (spread: number): string => {
  return spread.toFixed(1);
};

export const formatTime = (timestamp: number): string => {
  const date = new Date(timestamp);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
};

export const formatDate = (timestamp: number): string => {
  const date = new Date(timestamp);
  return date.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
};

export const formatDateTime = (timestamp: number): string => {
  const date = new Date(timestamp);
  return date.toLocaleString([], { 
    month: 'short', 
    day: 'numeric', 
    hour: '2-digit', 
    minute: '2-digit',
    second: '2-digit',
  });
};

export const formatDuration = (milliseconds: number): string => {
  const totalSeconds = Math.floor(milliseconds / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  } else if (minutes > 0) {
    return `${minutes}m ${seconds}s`;
  } else {
    return `${seconds}s`;
  }
};

export const formatRelativeTime = (timestamp: number): string => {
  const now = Date.now();
  const diff = now - timestamp;

  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (seconds < 60) {
    return `${seconds}s ago`;
  } else if (minutes < 60) {
    return `${minutes}m ago`;
  } else if (hours < 24) {
    return `${hours}h ago`;
  } else if (days < 7) {
    return `${days}d ago`;
  } else {
    return formatDate(timestamp);
  }
};

export const formatVolume = (volume: number, decimals = 2): string => {
  if (volume >= 1000000) {
    return `${(volume / 1000000).toFixed(decimals)}M`;
  } else if (volume >= 1000) {
    return `${(volume / 1000).toFixed(decimals)}K`;
  } else {
    return volume.toFixed(decimals);
  }
};

export const getPnlColorClass = (value: number): string => {
  if (value > 0) return 'text-kg-success';
  if (value < 0) return 'text-kg-danger';
  return 'text-kg-muted';
};

export const getPnlBgColorClass = (value: number): string => {
  if (value > 0) return 'bg-kg-success/10';
  if (value < 0) return 'bg-kg-danger/10';
  return 'bg-kg-panel';
};

export const getStatusBadgeColor = (status: string): { bg: string; text: string } => {
  switch (status) {
    case 'RUNNING':
      return { bg: 'bg-kg-success/10', text: 'text-kg-success' };
    case 'STOPPED':
      return { bg: 'bg-kg-muted/10', text: 'text-kg-muted' };
    case 'PAUSED':
      return { bg: 'bg-yellow-500/10', text: 'text-yellow-400' };
    case 'ERROR':
      return { bg: 'bg-kg-danger/10', text: 'text-kg-danger' };
    default:
      return { bg: 'bg-kg-panel', text: 'text-kg-text' };
  }
};

export const getRiskLevelColor = (
  current: number,
  max: number
): { bg: string; text: string } => {
  const percent = (current / max) * 100;
  if (percent > 80) {
    return { bg: 'bg-kg-danger/10', text: 'text-kg-danger' };
  } else if (percent > 60) {
    return { bg: 'bg-yellow-500/10', text: 'text-yellow-400' };
  } else {
    return { bg: 'bg-kg-success/10', text: 'text-kg-success' };
  }
};

export const formatRiskLevel = (
  current: number,
  max: number
): 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' => {
  const percent = (current / max) * 100;
  if (percent > 90) return 'CRITICAL';
  if (percent > 75) return 'HIGH';
  if (percent > 50) return 'MEDIUM';
  return 'LOW';
};
