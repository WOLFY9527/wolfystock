/**
 * useAutocomplete Hook
 *
 * Manage autocomplete interaction logic
 */

import { useState, useRef, useEffect } from 'react';
import type { StockIndexItem, StockSuggestion } from '../types/stockIndex';
import { searchStocks } from '../utils/searchStocks';
import { SEARCH_CONFIG } from '../utils/stockIndexFields';

export interface UseAutocompleteOptions {
  /** Minimum query length */
  minLength?: number;
  /** Debounce delay (milliseconds) */
  debounceMs?: number;
  /** Limit on number of results to return */
  limit?: number;
}

export interface UseAutocompleteResult {
  /** Current query string */
  query: string;
  /** Set query string */
  setQuery: (value: string) => void;
  /** Search suggestions list */
  suggestions: StockSuggestion[];
  /** Whether to show suggestions list */
  isOpen: boolean;
  /** Highlighted item index */
  highlightedIndex: number;
  /** Set highlighted item index */
  setHighlightedIndex: (index: number) => void;
  /** Highlight previous item */
  highlightPrevious: () => void;
  /** Highlight next item */
  highlightNext: () => void;
  /** Select suggestion item */
  handleSelect: (suggestion: StockSuggestion) => void;
  /** Close suggestions list */
  close: () => void;
  /** Reset state */
  reset: () => void;
  /** Whether IME is composing */
  isComposing: boolean;
  /** Set IME composing state */
  setIsComposing: (composing: boolean) => void;
  /** Whether runtime fallback mode is active */
  runtimeFallback: boolean;
  /** Runtime error captured from search flow */
  error: Error | null;
}

/**
 * Autocomplete Hook
 *
 * @param index - Stock index
 * @param options - Configuration options
 * @returns Autocomplete state and methods
 */
export function useAutocomplete(
  index: StockIndexItem[],
  options: UseAutocompleteOptions = {}
): UseAutocompleteResult {
  const {
    minLength = SEARCH_CONFIG.MIN_QUERY_LENGTH,
    debounceMs = SEARCH_CONFIG.DEBOUNCE_MS,
    limit = SEARCH_CONFIG.DEFAULT_LIMIT,
  } = options;

  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<StockSuggestion[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState<number>(-1);
  const [isComposing, setIsComposing] = useState(false);
  const [runtimeFallback, setRuntimeFallback] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // Use ref to store debounce timer
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Search function (debounced)
  const search = (q: string) => {
    if (runtimeFallback) {
      return;
    }

    if (q.length < minLength) {
      setSuggestions([]);
      setIsOpen(false);
      setHighlightedIndex(-1);
      return;
    }

    try {
      const results = searchStocks(q, index, { limit });
      setSuggestions(results);
      setIsOpen(results.length > 0);
      setHighlightedIndex(-1);
    } catch (caught) {
      const runtimeError = caught instanceof Error ? caught : new Error('Autocomplete search failed');
      console.error('Autocomplete search failed. Falling back to plain input.', runtimeError);
      setError(runtimeError);
      setRuntimeFallback(true);
      setSuggestions([]);
      setIsOpen(false);
      setHighlightedIndex(-1);
    }
  };

  // Input handling (with debounce)
  const handleInputChange = (value: string) => {
    setQuery(value);

    // Clear previous timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    if (runtimeFallback) {
      return;
    }

    // Set new timer
    debounceTimerRef.current = setTimeout(() => {
      search(value);
    }, debounceMs);
  };

  // Select suggestion item
  const handleSelect = (suggestion: StockSuggestion) => {
    setQuery(suggestion.displayCode);
    setIsOpen(false);
    setSuggestions([]);
    setHighlightedIndex(-1);
  };

  // Highlight previous item
  const highlightPrevious = () => {
    setHighlightedIndex(prev => {
      if (prev <= 0) return suggestions.length - 1;
      return prev - 1;
    });
  };

  // Highlight next item
  const highlightNext = () => {
    setHighlightedIndex(prev => {
      if (prev >= suggestions.length - 1) return 0;
      return prev + 1;
    });
  };

  // Close dropdown
  const close = () => {
    setIsOpen(false);
    setHighlightedIndex(-1);
  };

  // Reset
  const reset = () => {
    setQuery('');
    setSuggestions([]);
    setIsOpen(false);
    setHighlightedIndex(-1);
  };

  // Cleanup timer (on component unmount)
  useEffect(() => {
    return () => {
      const pendingTimer = debounceTimerRef.current;
      if (pendingTimer) {
        clearTimeout(pendingTimer);
      }
    };
  }, []);

  return {
    query,
    setQuery: handleInputChange,
    suggestions,
    isOpen,
    highlightedIndex,
    setHighlightedIndex,
    highlightPrevious,
    highlightNext,
    handleSelect,
    close,
    reset,
    isComposing,
    setIsComposing,
    runtimeFallback,
    error,
  };
}

/**
 * Get default exported Hook
 */
export default useAutocomplete;
