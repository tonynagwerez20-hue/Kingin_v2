import { useEffect, useRef, useState, useCallback } from 'react';
import useStore from '../store/useStore';

export interface WebSocketMessage {
  type: string;
  payload: any;
  timestamp: number;
}

export interface UseWebSocketOptions {
  url: string;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  onMessage?: (message: WebSocketMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
}

export function useWebSocket(options: UseWebSocketOptions) {
  const {
    url,
    reconnectInterval = 5000,
    maxReconnectAttempts = 5,
    onMessage,
    onConnect,
    onDisconnect,
    onError,
  } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const [isConnected, setIsConnected] = useState(false);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        reconnectAttemptsRef.current = 0;
        onConnect?.();
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          onMessage?.(message);
        } catch {
          console.warn('Failed to parse WebSocket message:', event.data);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        onDisconnect?.();

        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current += 1;
          setTimeout(connect, reconnectInterval);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        onError?.(error);
      };
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
    }
  }, [url, reconnectInterval, maxReconnectAttempts, onConnect, onDisconnect, onError, onMessage]);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  return { isConnected };
}

export function useSystemWebSocket() {
  const { syncWithEngine } = useStore();
  
  useWebSocket({
    url: 'ws://127.0.0.1:8088/ws/stream',
    onMessage: (message) => {
      if (message.type === 'STATE_UPDATE') {
        // We could manually update store here or just trigger a sync
        // For simplicity, we'll let syncWithEngine handle the complex mapping
        syncWithEngine();
      }
    },
  });
}