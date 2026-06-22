import { useStore } from "../store";
import type { SamsEvent } from "../types";

// Connects to the SAMS WebSocket stream, applies the snapshot, and feeds live
// events into the store. Auto-reconnects with backoff.
export function connectStream(space = "main.space"): () => void {
  let ws: WebSocket | null = null;
  let closed = false;
  let backoff = 500;

  const url = () => {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    return `${proto}://${location.host}/api/v1/stream?space=${encodeURIComponent(space)}`;
  };

  const open = () => {
    ws = new WebSocket(url());
    ws.onopen = () => {
      backoff = 500;
      useStore.getState().setConnected(true);
    };
    ws.onmessage = (msg) => {
      const data = JSON.parse(msg.data);
      if (data.type === "snapshot") useStore.getState().applySnapshot(data);
      else if (data.type === "event") useStore.getState().applyEvent(data.event as SamsEvent);
    };
    ws.onclose = () => {
      useStore.getState().setConnected(false);
      if (!closed) {
        setTimeout(open, backoff);
        backoff = Math.min(backoff * 2, 8000);
      }
    };
    ws.onerror = () => ws?.close();
  };

  open();
  return () => {
    closed = true;
    ws?.close();
  };
}
