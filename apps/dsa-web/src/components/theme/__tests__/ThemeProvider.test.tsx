import type React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  DEFAULT_THEME_MODE,
  THEME_MODE_STORAGE_KEY,
  THEME_STYLE_STORAGE_KEY,
  useThemeStyle,
} from '../themeState';
import { ThemeProvider } from '../ThemeProvider';

const ThemeProbe: React.FC = () => {
  const { colorMode, setColorMode, themeStyle } = useThemeStyle();
  return (
    <div>
      <p data-testid="theme-style">{themeStyle}</p>
      <p data-testid="theme-mode">{colorMode}</p>
      <button type="button" onClick={() => setColorMode('light')}>set light</button>
      <button type="button" onClick={() => setColorMode('dark')}>set dark</button>
    </div>
  );
};

function renderThemeProbe() {
  return render(
    <ThemeProvider>
      <ThemeProbe />
    </ThemeProvider>
  );
}

describe('ThemeProvider', () => {
  beforeAll(() => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: query === '(prefers-color-scheme: dark)',
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
  });

  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.removeAttribute('class');
    document.documentElement.removeAttribute('data-theme');
    document.documentElement.removeAttribute('data-theme-style');
    document.documentElement.removeAttribute('data-color-mode');
    document.body.removeAttribute('class');
    document.body.removeAttribute('data-theme');
    document.body.removeAttribute('data-theme-style');
    document.body.removeAttribute('data-color-mode');
  });

  it('keeps SpaceX as the default visual style while defaulting to dark mode', async () => {
    renderThemeProbe();

    await waitFor(() => expect(document.documentElement).toHaveAttribute('data-theme', DEFAULT_THEME_MODE));
    expect(document.documentElement).toHaveAttribute('data-theme-style', 'spacex');
    expect(document.body).toHaveAttribute('data-theme', DEFAULT_THEME_MODE);
    expect(document.body).toHaveAttribute('data-theme-style', 'spacex');
    expect(screen.getByTestId('theme-style')).toHaveTextContent('spacex');
    expect(screen.getByTestId('theme-mode')).toHaveTextContent(DEFAULT_THEME_MODE);
    expect(window.localStorage.getItem(THEME_STYLE_STORAGE_KEY)).toBe('spacex');
    expect(window.localStorage.getItem(THEME_MODE_STORAGE_KEY)).toBe(DEFAULT_THEME_MODE);
  });

  it('changes data-theme when switching between light and dark modes', async () => {
    renderThemeProbe();

    fireEvent.click(screen.getByRole('button', { name: 'set light' }));

    await waitFor(() => expect(document.documentElement).toHaveAttribute('data-theme', 'light'));
    expect(document.documentElement).toHaveClass('light');
    expect(document.documentElement).not.toHaveClass('dark');
    expect(document.body).toHaveAttribute('data-theme', 'light');
    expect(screen.getByTestId('theme-mode')).toHaveTextContent('light');
    expect(window.localStorage.getItem(THEME_MODE_STORAGE_KEY)).toBe('light');

    fireEvent.click(screen.getByRole('button', { name: 'set dark' }));

    await waitFor(() => expect(document.documentElement).toHaveAttribute('data-theme', 'dark'));
    expect(document.documentElement).toHaveClass('dark');
    expect(document.documentElement).not.toHaveClass('light');
    expect(document.body).toHaveAttribute('data-theme', 'dark');
    expect(screen.getByTestId('theme-mode')).toHaveTextContent('dark');
    expect(window.localStorage.getItem(THEME_MODE_STORAGE_KEY)).toBe('dark');
  });

  it('restores the saved light preference when persistence exists', async () => {
    window.localStorage.setItem(THEME_MODE_STORAGE_KEY, 'light');
    window.localStorage.setItem(THEME_STYLE_STORAGE_KEY, 'spacex');

    renderThemeProbe();

    await waitFor(() => expect(document.documentElement).toHaveAttribute('data-theme', 'light'));
    expect(screen.getByTestId('theme-mode')).toHaveTextContent('light');
    expect(document.documentElement).toHaveAttribute('data-theme-style', 'spacex');
    expect(window.localStorage.getItem(THEME_MODE_STORAGE_KEY)).toBe('light');
  });

  it('falls back safely when stored theme values are invalid', async () => {
    window.localStorage.setItem(THEME_MODE_STORAGE_KEY, 'spacex');
    window.localStorage.setItem(THEME_STYLE_STORAGE_KEY, 'neon');

    renderThemeProbe();

    await waitFor(() => expect(document.documentElement).toHaveAttribute('data-theme', DEFAULT_THEME_MODE));
    expect(screen.getByTestId('theme-mode')).toHaveTextContent(DEFAULT_THEME_MODE);
    expect(document.documentElement).toHaveAttribute('data-theme-style', 'spacex');
    expect(window.localStorage.getItem(THEME_MODE_STORAGE_KEY)).toBe(DEFAULT_THEME_MODE);
    expect(window.localStorage.getItem(THEME_STYLE_STORAGE_KEY)).toBe('spacex');
  });
});
