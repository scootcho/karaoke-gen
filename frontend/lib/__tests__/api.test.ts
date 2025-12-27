/**
 * Tests for API client
 */

import { api, ApiError, extractErrorMessage } from "../api"

// Mock fetch globally
global.fetch = jest.fn()

describe("API Client", () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  describe("listJobs", () => {
    it("should fetch jobs successfully", async () => {
      const mockJobs = [
        { job_id: "1", status: "complete", artist: "Test Artist", title: "Test Song" },
      ]

      ;(global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockJobs,
      })

      const result = await api.listJobs()
      expect(result).toEqual(mockJobs)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/jobs"),
        expect.any(Object)
      )
    })

    it("should handle errors", async () => {
      ;(global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ detail: "Server error" }),
      })

      await expect(api.listJobs()).rejects.toThrow(ApiError)
    })

    it("should include query parameters", async () => {
      ;(global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      })

      await api.listJobs({ status: "complete", limit: 10 })
      const callArgs = (global.fetch as jest.Mock).mock.calls[0][0]
      expect(callArgs).toContain("status=complete")
      expect(callArgs).toContain("limit=10")
    })
  })

  describe("getJob", () => {
    it("should fetch a single job", async () => {
      const mockJob = { job_id: "123", status: "complete" }

      ;(global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockJob,
      })

      const result = await api.getJob("123")
      expect(result).toEqual(mockJob)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/jobs/123"),
        expect.any(Object)
      )
    })
  })

  describe("uploadJob", () => {
    it("should upload a file and create a job", async () => {
      const mockFile = new File(["test"], "test.mp3", { type: "audio/mpeg" })
      const mockResponse = { status: "success", job_id: "123" }

      ;(global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      })

      const result = await api.uploadJob(mockFile, "Artist", "Title")
      expect(result).toEqual(mockResponse)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/jobs/upload"),
        expect.objectContaining({ method: "POST" })
      )
    })
  })

  describe("searchAudio", () => {
    it("should search for audio", async () => {
      const mockResponse = {
        status: "success",
        job_id: "123",
        results: [],
        total_results: 0,
      }

      ;(global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      })

      const result = await api.searchAudio("Artist", "Title")
      expect(result).toEqual(mockResponse)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/audio-search/search"),
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({ "Content-Type": "application/json" }),
        })
      )
    })
  })

  describe("getJobLogs", () => {
    it("should fetch job logs", async () => {
      const mockLogs = [
        { timestamp: "2025-01-01T00:00:00Z", level: "INFO", message: "Test log" },
      ]

      ;(global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ logs: mockLogs }),
      })

      const result = await api.getJobLogs("123")
      expect(result).toEqual(mockLogs)
      const callArgs = (global.fetch as jest.Mock).mock.calls[0][0]
      expect(callArgs).toContain("/api/jobs/123/logs")
    })

    it("should handle missing logs field", async () => {
      ;(global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      })

      const result = await api.getJobLogs("123")
      expect(result).toEqual([])
    })
  })

  describe("cancelJob", () => {
    it("should cancel a job", async () => {
      const mockResponse = { status: "success", message: "Job cancelled" }

      ;(global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      })

      const result = await api.cancelJob("123", "User requested")
      expect(result).toEqual(mockResponse)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/jobs/123/cancel"),
        expect.objectContaining({ method: "POST" })
      )
    })
  })

  describe("retryJob", () => {
    it("should retry a failed job", async () => {
      const mockResponse = { status: "success", job_id: "123", message: "Job retried" }

      ;(global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      })

      const result = await api.retryJob("123")
      expect(result).toEqual(mockResponse)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/jobs/123/retry"),
        expect.objectContaining({ method: "POST" })
      )
    })
  })

  describe("completeReview", () => {
    it("should complete lyrics review", async () => {
      const mockResponse = { status: "success", job_status: "review_complete", message: "Review completed" }

      ;(global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      })

      const result = await api.completeReview("123")
      expect(result).toEqual(mockResponse)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/jobs/123/complete-review"),
        expect.objectContaining({ method: "POST" })
      )
    })
  })

  describe("selectInstrumental", () => {
    it("should select instrumental", async () => {
      const mockResponse = { status: "success", job_status: "instrumental_selected", selection: "clean", message: "Instrumental selected" }

      ;(global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      })

      const result = await api.selectInstrumental("123", "clean")
      expect(result).toEqual(mockResponse)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/jobs/123/select-instrumental"),
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({ "Content-Type": "application/json" }),
        })
      )
    })
  })

  describe("selectAudioResult", () => {
    it("should select audio search result", async () => {
      const mockResponse = { status: "success", message: "Audio selected" }

      ;(global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      })

      const result = await api.selectAudioResult("123", 0)
      expect(result).toEqual(mockResponse)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/audio-search/123/select"),
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({ "Content-Type": "application/json" }),
        })
      )
    })
  })
})

describe("extractErrorMessage", () => {
  const fallback = "Default error message"

  it("should extract string detail field", () => {
    expect(extractErrorMessage({ detail: "Error from detail" }, fallback)).toBe("Error from detail")
  })

  it("should extract string message field", () => {
    expect(extractErrorMessage({ message: "Error from message" }, fallback)).toBe("Error from message")
  })

  it("should extract string error field", () => {
    expect(extractErrorMessage({ error: "Error from error field" }, fallback)).toBe("Error from error field")
  })

  it("should prefer detail over message", () => {
    expect(extractErrorMessage({ detail: "Detail", message: "Message" }, fallback)).toBe("Detail")
  })

  it("should extract nested detail.message", () => {
    expect(extractErrorMessage({ detail: { message: "Nested message" } }, fallback)).toBe("Nested message")
  })

  it("should extract nested detail.error", () => {
    expect(extractErrorMessage({ detail: { error: "Nested error" } }, fallback)).toBe("Nested error")
  })

  it("should stringify object detail", () => {
    const objDetail = { code: "ERR_001", info: "More info" }
    expect(extractErrorMessage({ detail: objDetail }, fallback)).toBe(JSON.stringify(objDetail))
  })

  it("should return fallback for null data", () => {
    expect(extractErrorMessage(null, fallback)).toBe(fallback)
  })

  it("should return fallback for undefined data", () => {
    expect(extractErrorMessage(undefined, fallback)).toBe(fallback)
  })

  it("should return fallback for empty object", () => {
    expect(extractErrorMessage({}, fallback)).toBe(fallback)
  })

  it("should return fallback for numeric detail (not a string)", () => {
    // Numbers are not extracted - only strings
    expect(extractErrorMessage({ detail: 123 }, fallback)).toBe(fallback)
  })

  it("should handle [object Object] case that caused the original bug", () => {
    // This is the case that caused [object Object] to be displayed
    const problematicData = { detail: { some: "object" } }
    const result = extractErrorMessage(problematicData, fallback)
    expect(result).not.toBe("[object Object]")
    expect(result).toBe('{"some":"object"}')
  })
})
