/**
 * Tests for API client
 */

import { api, ApiError } from "../api"

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
        expect.stringContaining("/api/jobs")
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
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("status=complete")
      )
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("limit=10")
      )
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
        expect.stringContaining("/api/jobs/123")
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
          headers: { "Content-Type": "application/json" },
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
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/jobs/123/logs")
      )
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
})

