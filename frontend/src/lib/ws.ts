"use client";
import { useEffect, useRef, useCallback } from "react";
import type { WsEvent } from "./types";

const GO_WS = process.env.NEXT_PUBLIC_GO_WS ?? "ws://localhost:8080/ws";

export function useWebSocket(onEvent: (e: WsEvent) => void) {
  const wsRef = useRef<WebSocket | null>(null);
  const cbRef = useRef(onEvent);
  cbRef.current = onEvent;

  const connect = useCallback(() => {
    const sock = new WebSocket(GO_WS);
    wsRef.current = sock;
    sock.onmessage = (e) => {
      try { cbRef.current(JSON.parse(e.data)); } catch {}
    };
    sock.onclose = () => { setTimeout(connect, 3000); };
  }, []);

  useEffect(() => {
    connect();
    return () => wsRef.current?.close();
  }, [connect]);
}
