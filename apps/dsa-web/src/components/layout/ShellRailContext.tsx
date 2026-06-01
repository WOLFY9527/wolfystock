import type React from 'react';
import { createContext } from 'react';

type ShellRailContextValue = {
  setRailContent: (content: React.ReactNode | null) => void;
  closeMobileRail: () => void;
  openRail: () => void;
  isConnected: boolean;
};

export const ShellRailContext = createContext<ShellRailContextValue>({
  setRailContent: () => undefined,
  closeMobileRail: () => undefined,
  openRail: () => undefined,
  isConnected: false,
});
