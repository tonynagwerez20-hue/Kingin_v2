// useWebSocket.ts - WebSocket connection hook for real-time data streaming

import { useEffect, useRef, useState, useCallback } from 'react';
import { useAppStore } from '../store/useAppStore';

export interface WebSocketMessage {
  type: string;
  payload: unknown;
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

export interface UseWebSocketReturn {
  isConnected: boolean;
  lastMessage: WebSocketMessage | null;
  sendMessage: (message: unknown) => void;
  reconnect: () => void;
  disconnect: () => void;
  connectionLatency: number | null;
}

export function useWebSocket(options: UseWebSocketOptions): UseWebSocketReturn {
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
  const pingIntervalRef = useRef<number | null>(null);
  const lastPingTimeRef = useRef<number>(0);

  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [connectionLatency, setConnectionLatency] = useState<number | null>(null);

  const { setWebSocketConnected, setSystemStatus } = useAppStore();

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setWebSocketConnected(true);
        setSystemStatus('LIVE');
        reconnectAttemptsRef.current = 0;
        onConnect?.();

        pingIntervalRef.current = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            lastPingTimeRef.current = Date.now();
            ws.send(JSON.stringify({ type: 'PING', timestamp: Date.now() }));
          }
        }, 10000);
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as WebSocketMessage;
          
          if (message.type === 'PONG') {
            const latency = Date.now() - lastPingTimeRef.current;
            setConnectionLatency(latency);
          } else {
            setLastMessage(message);
            onMessage?.(message);
          }
        } catch {
          console.warn('Failed to parse WebSocket message:', event.data);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        setWebSocketConnected(false);
        setSystemStatus('OFFLINE');
        
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }

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
      setSystemStatus('OFFLINE');
    }
  }, [url, reconnectInterval, maxReconnectAttempts, onConnect, onDisconnect, onError, onMessage, setWebSocketConnected, setSystemStatus]);

  const sendMessage = useCallback((message: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  const reconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
    }
    reconnectAttemptsRef.current = 0;
    connect();
  }, [connect]);

  const disconnect = useCallback(() => {
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    reconnectAttemptsRef.current = maxReconnectAttempts;
  }, [maxReconnectAttempts]);

  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    isConnected,
    lastMessage,
    sendMessage,
    reconnect,
    disconnect,
    connectionLatency,
  };
}

export function usePositionsWebSocket() {
  const { lastMessage, isConnected } = useWebSocket({
    url: 'ws://localhost:8080/stream',
    onMessage: (message) => {
      console.log('Position update:', message);
    },
  });

  return { lastMessage, isConnected };
}

export function useMarketPricesWebSocket() {
  const { lastMessage, isConnected } = useWebSocket({
    url: 'ws://localhost:8080/stream',
    onMessage: (message) => {
      console.log('Market price update:', message);
    },
  });

  return { lastMessage, isConnected };
}

export function useSystemLogsWebSocket() {
  const [logs, setLogs] = useState<WebSocketMessage[]>([]);

  const { lastMessage, isConnected } = useWebSocket({
    url: 'ws://localhost:8080/stream',
    onMessage: (message) => {
      if (message.type === 'LOG') {
        setLogs((prev) => [message, ...prev].slice(0, 500));
      }
    },
  });

  return { logs, lastMessage, isConnected };
}