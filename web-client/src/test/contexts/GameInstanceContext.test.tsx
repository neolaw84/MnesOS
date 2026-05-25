import { describe, it, expect, vi } from 'vitest';
import { render, renderHook, act, screen } from '@testing-library/react';
import { GameInstanceProvider, useGameInstance } from '../../contexts/GameInstanceContext';

describe('GameInstanceContext', () => {
  describe('useGameInstance outside provider', () => {
    it('throws when used outside GameInstanceProvider', () => {
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
      expect(() => {
        renderHook(() => useGameInstance());
      }).toThrow();
      consoleError.mockRestore();
    });
  });

  describe('default state', () => {
    it('provides activeInstanceId=null initially', () => {
      const { result } = renderHook(() => useGameInstance(), {
        wrapper: ({ children }) => <GameInstanceProvider>{children}</GameInstanceProvider>,
      });
      expect(result.current.activeInstanceId).toBeNull();
    });

    it('provides minigameOpen=false initially', () => {
      const { result } = renderHook(() => useGameInstance(), {
        wrapper: ({ children }) => <GameInstanceProvider>{children}</GameInstanceProvider>,
      });
      expect(result.current.minigameOpen).toBe(false);
    });

    it('exposes setActiveInstanceId as a function', () => {
      const { result } = renderHook(() => useGameInstance(), {
        wrapper: ({ children }) => <GameInstanceProvider>{children}</GameInstanceProvider>,
      });
      expect(typeof result.current.setActiveInstanceId).toBe('function');
    });

    it('exposes setMinigameOpen as a function', () => {
      const { result } = renderHook(() => useGameInstance(), {
        wrapper: ({ children }) => <GameInstanceProvider>{children}</GameInstanceProvider>,
      });
      expect(typeof result.current.setMinigameOpen).toBe('function');
    });
  });

  describe('setters', () => {
    it('can update activeInstanceId', () => {
      const { result } = renderHook(() => useGameInstance(), {
        wrapper: ({ children }) => <GameInstanceProvider>{children}</GameInstanceProvider>,
      });
      act(() => {
        result.current.setActiveInstanceId('instance-1');
      });
      expect(result.current.activeInstanceId).toBe('instance-1');
    });

    it('can update minigameOpen to true', () => {
      const { result } = renderHook(() => useGameInstance(), {
        wrapper: ({ children }) => <GameInstanceProvider>{children}</GameInstanceProvider>,
      });
      act(() => {
        result.current.setMinigameOpen(true);
      });
      expect(result.current.minigameOpen).toBe(true);
    });

    it('can set activeInstanceId back to null', () => {
      const { result } = renderHook(() => useGameInstance(), {
        wrapper: ({ children }) => <GameInstanceProvider>{children}</GameInstanceProvider>,
      });
      act(() => {
        result.current.setActiveInstanceId('instance-1');
      });
      act(() => {
        result.current.setActiveInstanceId(null);
      });
      expect(result.current.activeInstanceId).toBeNull();
    });

    it('can toggle minigameOpen back to false', () => {
      const { result } = renderHook(() => useGameInstance(), {
        wrapper: ({ children }) => <GameInstanceProvider>{children}</GameInstanceProvider>,
      });
      act(() => {
        result.current.setMinigameOpen(true);
      });
      act(() => {
        result.current.setMinigameOpen(false);
      });
      expect(result.current.minigameOpen).toBe(false);
    });
  });

  describe('rendering', () => {
    it('renders children', () => {
      render(
        <GameInstanceProvider>
          <div data-testid="child">Hello</div>
        </GameInstanceProvider>
      );
      expect(screen.getByTestId('child')).toBeInTheDocument();
    });
  });
});
