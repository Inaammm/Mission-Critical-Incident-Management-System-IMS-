import { useEffect, useRef, useState, useCallback } from 'react';

export function useWebSocket(url: string) {
  const ws = useRef<WebSocket | null>(null);
  const [lastMessage, setLastMessage] = useState<any>(null);
  const [isConnected, setIsConnected] = useState(false);

  const connect = useCallback(() => {
    const wsUrl = url.startsWith('ws') ? url : `ws://localhost:8000${url}`;
    ws.current = new WebSocket(wsUrl);

    ws.current.onopen = () => setIsConnected(true);
    ws.current.onclose = () => {
      setIsConnected(false);
      setTimeout(connect, 3000); // Auto-reconnect
    };
    ws.current.onmessage = (event) => {
      try {
        setLastMessage(JSON.parse(event.data));
      } catch {}
    };
  }, [url]);

  useEffect(() => {
    connect();
    return () => { ws.current?.close(); };
  }, [connect]);

  return { lastMessage, isConnected };
}
