/**
 * Tests for auto-mode state management
 */

import { renderHook, act } from "@testing-library/react"
import { useAutoMode, getAutoModeFromUrl } from "../auto-mode"

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: jest.fn((key: string) => store[key] || null),
    setItem: jest.fn((key: string, value: string) => {
      store[key] = value
    }),
    removeItem: jest.fn((key: string) => {
      delete store[key]
    }),
    clear: jest.fn(() => {
      store = {}
    }),
  }
})()

Object.defineProperty(window, "localStorage", { value: localStorageMock })

describe("Auto Mode", () => {
  beforeEach(() => {
    localStorageMock.clear()
    jest.clearAllMocks()
  })

  describe("useAutoMode hook", () => {
    it("should initialize with enabled=false", () => {
      const { result } = renderHook(() => useAutoMode())
      expect(result.current.enabled).toBe(false)
    })

    it("should enable auto-mode", () => {
      const { result } = renderHook(() => useAutoMode())

      act(() => {
        result.current.enable()
      })

      expect(result.current.enabled).toBe(true)
    })

    it("should disable auto-mode", () => {
      const { result } = renderHook(() => useAutoMode())

      act(() => {
        result.current.enable()
        result.current.disable()
      })

      expect(result.current.enabled).toBe(false)
    })

    it("should toggle auto-mode", () => {
      const { result } = renderHook(() => useAutoMode())

      act(() => {
        result.current.toggle()
      })
      expect(result.current.enabled).toBe(true)

      act(() => {
        result.current.toggle()
      })
      expect(result.current.enabled).toBe(false)
    })

    it("should set enabled directly", () => {
      const { result } = renderHook(() => useAutoMode())

      act(() => {
        result.current.setEnabled(true)
      })
      expect(result.current.enabled).toBe(true)

      act(() => {
        result.current.setEnabled(false)
      })
      expect(result.current.enabled).toBe(false)
    })

    it("should track processing jobs", () => {
      const { result } = renderHook(() => useAutoMode())

      expect(result.current.isProcessing("job-123-review")).toBe(false)

      act(() => {
        result.current.markProcessing("job-123-review")
      })

      expect(result.current.isProcessing("job-123-review")).toBe(true)
      expect(result.current.isProcessing("job-456-review")).toBe(false)

      act(() => {
        result.current.unmarkProcessing("job-123-review")
      })

      expect(result.current.isProcessing("job-123-review")).toBe(false)
    })

    it("should handle multiple processing jobs", () => {
      const { result } = renderHook(() => useAutoMode())

      act(() => {
        result.current.markProcessing("job-1-review")
        result.current.markProcessing("job-2-instrumental")
      })

      expect(result.current.isProcessing("job-1-review")).toBe(true)
      expect(result.current.isProcessing("job-2-instrumental")).toBe(true)

      act(() => {
        result.current.unmarkProcessing("job-1-review")
      })

      expect(result.current.isProcessing("job-1-review")).toBe(false)
      expect(result.current.isProcessing("job-2-instrumental")).toBe(true)
    })
  })

  describe("getAutoModeFromUrl", () => {
    const originalLocation = window.location

    beforeEach(() => {
      // @ts-ignore - mocking location
      delete window.location
      // @ts-ignore - mocking location
      window.location = { search: "" }
    })

    afterEach(() => {
      window.location = originalLocation
    })

    it("should return false when no auto parameter", () => {
      // @ts-ignore
      window.location.search = ""
      expect(getAutoModeFromUrl()).toBe(false)
    })

    it('should return true when auto=true', () => {
      // @ts-ignore
      window.location.search = "?auto=true"
      expect(getAutoModeFromUrl()).toBe(true)
    })

    it('should return true when auto=1', () => {
      // @ts-ignore
      window.location.search = "?auto=1"
      expect(getAutoModeFromUrl()).toBe(true)
    })

    it('should return false when auto=false', () => {
      // @ts-ignore
      window.location.search = "?auto=false"
      expect(getAutoModeFromUrl()).toBe(false)
    })

    it("should handle multiple query params", () => {
      // @ts-ignore
      window.location.search = "?foo=bar&auto=true&baz=qux"
      expect(getAutoModeFromUrl()).toBe(true)
    })
  })
})
