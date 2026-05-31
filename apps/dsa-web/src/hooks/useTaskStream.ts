import { useEffect, useRef, useSyncExternalStore } from 'react';
import { analysisApi } from '../api/analysis';
import { toCamelCase } from '../api/utils';
import type { TaskInfo } from '../types/analysis';

/**
 * SSE event types.
 */
export type SSEEventType =
  | 'connected'
  | 'task_created'
  | 'task_started'
  | 'task_updated'
  | 'task_completed'
  | 'task_failed'
  | 'heartbeat';

/**
 * SSE event payload.
 */
export interface SSEEvent {
  type: SSEEventType;
  task?: TaskInfo;
  timestamp?: string;
}

/**
 * SSE hook options.
 */
export interface UseTaskStreamOptions {
  /** Task created callback */
  onTaskCreated?: (task: TaskInfo) => void;
  /** Task started callback */
  onTaskStarted?: (task: TaskInfo) => void;
  /** Task updated callback */
  onTaskUpdated?: (task: TaskInfo) => void;
  /** Task completed callback */
  onTaskCompleted?: (task: TaskInfo) => void;
  /** Task failed callback */
  onTaskFailed?: (task: TaskInfo) => void;
  /** Connected callback */
  onConnected?: () => void;
  /** Connection error callback */
  onError?: (error: Event) => void;
  /** Whether to reconnect automatically */
  autoReconnect?: boolean;
  /** Reconnect delay in milliseconds */
  reconnectDelay?: number;
  /** Whether the hook is enabled */
  enabled?: boolean;
}

/**
 * SSE hook result.
 */
export interface UseTaskStreamResult {
  /** Whether the stream is connected */
  isConnected: boolean;
  /** Reconnect manually */
  reconnect: () => void;
  /** Disconnect manually */
  disconnect: () => void;
}

function parseTaskStreamEventData(eventData: string): TaskInfo | null {
  try {
    const data = JSON.parse(eventData);
    return toCamelCase<TaskInfo>(data);
  } catch (error) {
    console.error('Failed to parse SSE event data:', error);
    return null;
  }
}

/**
 * Task-stream SSE hook for realtime task status updates.
 */
export function useTaskStream(options: UseTaskStreamOptions = {}): UseTaskStreamResult {
  const {
    onTaskCreated,
    onTaskStarted,
    onTaskUpdated,
    onTaskCompleted,
    onTaskFailed,
    onConnected,
    onError,
    autoReconnect = true,
    reconnectDelay = 3000,
    enabled = true,
  } = options;

  const eventSourceRef = useRef<EventSource | null>(null);
  const isConnectedRef = useRef(false);
  const listenersRef = useRef<Set<() => void> | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const connectRef = useRef<() => void>(() => {});
  const disconnectRef = useRef<() => void>(() => {});
  const isConnected = useSyncExternalStore(
    (listener) => {
      const listeners = listenersRef.current ?? (listenersRef.current = new Set());
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    () => (enabled ? isConnectedRef.current : false),
    () => false,
  );

  // Store callbacks in a ref to avoid reconnecting on every render.
  const callbacksRef = useRef({
    onTaskCreated,
    onTaskStarted,
    onTaskUpdated,
    onTaskCompleted,
    onTaskFailed,
    onConnected,
    onError,
  });

  // Keep the latest callbacks available to the active SSE handlers.
  useEffect(() => {
    callbacksRef.current = {
      onTaskCreated,
      onTaskStarted,
      onTaskUpdated,
      onTaskCompleted,
      onTaskFailed,
      onConnected,
      onError,
    };
  });

  // Connect or disconnect when the hook is enabled or disabled.
  useEffect(() => {
    const notifyConnectionChange = (nextValue: boolean) => {
      if (isConnectedRef.current === nextValue) {
        return;
      }
      isConnectedRef.current = nextValue;
      const listeners = listenersRef.current;
      if (!listeners) {
        return;
      }
      listeners.forEach((listener) => listener());
    };

    const doConnect = () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }

      const url = analysisApi.getTaskStreamUrl();
      const eventSource = new EventSource(url, { withCredentials: true });
      eventSourceRef.current = eventSource;

      // Connected event
      eventSource.addEventListener('connected', () => {
        notifyConnectionChange(true);
        callbacksRef.current.onConnected?.();
      });

      // Task created event
      eventSource.addEventListener('task_created', (e) => {
        const task = parseTaskStreamEventData(e.data);
        if (task) callbacksRef.current.onTaskCreated?.(task);
      });

      // Task started event
      eventSource.addEventListener('task_started', (e) => {
        const task = parseTaskStreamEventData(e.data);
        if (task) callbacksRef.current.onTaskStarted?.(task);
      });

      // Task updated event
      eventSource.addEventListener('task_updated', (e) => {
        const task = parseTaskStreamEventData(e.data);
        if (task) callbacksRef.current.onTaskUpdated?.(task);
      });

      // Task completed event
      eventSource.addEventListener('task_completed', (e) => {
        const task = parseTaskStreamEventData(e.data);
        if (task) callbacksRef.current.onTaskCompleted?.(task);
      });

      // Task failed event
      eventSource.addEventListener('task_failed', (e) => {
        const task = parseTaskStreamEventData(e.data);
        if (task) callbacksRef.current.onTaskFailed?.(task);
      });

      // Heartbeat event used to keep the connection alive.
      eventSource.addEventListener('heartbeat', () => {
        // Optional place to record the latest heartbeat timestamp.
      });

      // Connection error handling
      eventSource.onerror = (error) => {
        notifyConnectionChange(false);
        callbacksRef.current.onError?.(error);

        // Auto-reconnect via ref to avoid stale closure issues.
        if (autoReconnect && enabled) {
          eventSource.close();
          reconnectTimeoutRef.current = setTimeout(() => {
            connectRef.current();
          }, reconnectDelay);
        }
      };
    };

    const doDisconnect = () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      notifyConnectionChange(false);
    };

    connectRef.current = doConnect;
    disconnectRef.current = doDisconnect;

    if (enabled) {
      doConnect();
    } else {
      doDisconnect();
    }

    return () => {
      doDisconnect();
    };
  }, [enabled, autoReconnect, reconnectDelay]);

  // Reconnect
  const reconnect = () => {
    disconnectRef.current();
    connectRef.current();
  };

  // Disconnect and defer the state update to avoid nested renders.
  const disconnect = () => {
    disconnectRef.current();
  };

  return {
    isConnected,
    reconnect,
    disconnect,
  };
}

export default useTaskStream;
