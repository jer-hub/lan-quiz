import { useEffect, useRef, useState } from "react";
import { io, Socket } from "socket.io-client";

let sharedSocket: Socket | null = null;

function getSocket(): Socket {
  if (!sharedSocket) {
    sharedSocket = io({
      path: "/socket.io",
      transports: ["websocket", "polling"],
      autoConnect: true,
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 500,
      reconnectionDelayMax: 5000,
    });
  }
  return sharedSocket;
}

const PLAYER_KEY = "lanquiz_join";
const HOST_KEY = "lanquiz_host";

export type StoredJoin = { pin: string; sid: string; nickname: string; student_code?: string };
export type StoredHost = { pin: string };

export function saveJoinSession(j: StoredJoin) {
  try {
    sessionStorage.setItem(PLAYER_KEY, JSON.stringify(j));
  } catch {
    /* ignore */
  }
}

export function loadJoinSession(): StoredJoin | null {
  try {
    const raw = sessionStorage.getItem(PLAYER_KEY);
    return raw ? (JSON.parse(raw) as StoredJoin) : null;
  } catch {
    return null;
  }
}

export function clearJoinSession() {
  try {
    sessionStorage.removeItem(PLAYER_KEY);
  } catch {
    /* ignore */
  }
}

export function saveHostSession(h: StoredHost) {
  try {
    sessionStorage.setItem(HOST_KEY, JSON.stringify(h));
  } catch {
    /* ignore */
  }
}

export function loadHostSession(): StoredHost | null {
  try {
    const raw = sessionStorage.getItem(HOST_KEY);
    return raw ? (JSON.parse(raw) as StoredHost) : null;
  } catch {
    return null;
  }
}

export function clearHostSession() {
  try {
    sessionStorage.removeItem(HOST_KEY);
  } catch {
    /* ignore */
  }
}

export function useSocket() {
  const socketRef = useRef<Socket>(getSocket());
  const [connected, setConnected] = useState(socketRef.current.connected);

  useEffect(() => {
    const socket = socketRef.current;

    const onConnect = () => setConnected(true);
    const onDisconnect = () => setConnected(false);

    socket.on("connect", onConnect);
    socket.on("disconnect", onDisconnect);
    setConnected(socket.connected);

    return () => {
      socket.off("connect", onConnect);
      socket.off("disconnect", onDisconnect);
    };
  }, []);

  return { socket: socketRef.current, connected };
}

export function useSocketEvent<T = unknown>(
  event: string,
  handler: (data: T) => void,
) {
  const { socket } = useSocket();
  const handlerRef = useRef(handler);
  handlerRef.current = handler;

  useEffect(() => {
    const listener = (data: T) => handlerRef.current(data);
    socket.on(event, listener);
    return () => {
      socket.off(event, listener);
    };
  }, [socket, event]);
}
