/**
 * Tests for JobActions component
 */

import { render, screen } from '@testing-library/react'
import { JobActions } from '../job/JobActions'
import { Job } from '@/lib/api'

// Mock the API module
jest.mock('@/lib/api', () => ({
  api: {
    retryJob: jest.fn(),
    cancelJob: jest.fn(),
    deleteJob: jest.fn(),
  }
}))

describe('JobActions', () => {
  const mockOnRefresh = jest.fn()
  const mockOnToggleLogs = jest.fn()

  const baseJob: Partial<Job> = {
    job_id: '123',
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
    artist: 'Test Artist',
    title: 'Test Song',
  }

  beforeEach(() => {
    jest.clearAllMocks()
  })

  describe('Retry button visibility', () => {
    it('shows retry button for failed jobs', () => {
      const failedJob = { ...baseJob, status: 'failed' } as Job
      render(
        <JobActions
          job={failedJob}
          onRefresh={mockOnRefresh}
          showLogs={false}
          onToggleLogs={mockOnToggleLogs}
        />
      )

      expect(screen.getByText('Retry')).toBeInTheDocument()
    })

    it('shows retry button for cancelled jobs', () => {
      const cancelledJob = { ...baseJob, status: 'cancelled' } as Job
      render(
        <JobActions
          job={cancelledJob}
          onRefresh={mockOnRefresh}
          showLogs={false}
          onToggleLogs={mockOnToggleLogs}
        />
      )

      expect(screen.getByText('Retry')).toBeInTheDocument()
    })

    it('does not show retry button for pending jobs', () => {
      const pendingJob = { ...baseJob, status: 'pending' } as Job
      render(
        <JobActions
          job={pendingJob}
          onRefresh={mockOnRefresh}
          showLogs={false}
          onToggleLogs={mockOnToggleLogs}
        />
      )

      expect(screen.queryByText('Retry')).not.toBeInTheDocument()
    })

    it('does not show retry button for processing jobs', () => {
      const processingJob = { ...baseJob, status: 'processing' } as Job
      render(
        <JobActions
          job={processingJob}
          onRefresh={mockOnRefresh}
          showLogs={false}
          onToggleLogs={mockOnToggleLogs}
        />
      )

      expect(screen.queryByText('Retry')).not.toBeInTheDocument()
    })

    it('does not show retry button for complete jobs', () => {
      const completeJob = { ...baseJob, status: 'complete' } as Job
      render(
        <JobActions
          job={completeJob}
          onRefresh={mockOnRefresh}
          showLogs={false}
          onToggleLogs={mockOnToggleLogs}
        />
      )

      expect(screen.queryByText('Retry')).not.toBeInTheDocument()
    })
  })

  describe('Cancel button visibility', () => {
    it('shows cancel button for pending jobs', () => {
      const pendingJob = { ...baseJob, status: 'pending' } as Job
      render(
        <JobActions
          job={pendingJob}
          onRefresh={mockOnRefresh}
          showLogs={false}
          onToggleLogs={mockOnToggleLogs}
        />
      )

      expect(screen.getByText('Cancel')).toBeInTheDocument()
    })

    it('does not show cancel button for failed jobs', () => {
      const failedJob = { ...baseJob, status: 'failed' } as Job
      render(
        <JobActions
          job={failedJob}
          onRefresh={mockOnRefresh}
          showLogs={false}
          onToggleLogs={mockOnToggleLogs}
        />
      )

      expect(screen.queryByText('Cancel')).not.toBeInTheDocument()
    })

    it('does not show cancel button for cancelled jobs', () => {
      const cancelledJob = { ...baseJob, status: 'cancelled' } as Job
      render(
        <JobActions
          job={cancelledJob}
          onRefresh={mockOnRefresh}
          showLogs={false}
          onToggleLogs={mockOnToggleLogs}
        />
      )

      expect(screen.queryByText('Cancel')).not.toBeInTheDocument()
    })
  })

  describe('Delete button visibility', () => {
    it('shows delete button for complete jobs', () => {
      const completeJob = { ...baseJob, status: 'complete' } as Job
      render(
        <JobActions
          job={completeJob}
          onRefresh={mockOnRefresh}
          showLogs={false}
          onToggleLogs={mockOnToggleLogs}
        />
      )

      expect(screen.getByText('Delete')).toBeInTheDocument()
    })

    it('shows delete button for failed jobs', () => {
      const failedJob = { ...baseJob, status: 'failed' } as Job
      render(
        <JobActions
          job={failedJob}
          onRefresh={mockOnRefresh}
          showLogs={false}
          onToggleLogs={mockOnToggleLogs}
        />
      )

      expect(screen.getByText('Delete')).toBeInTheDocument()
    })

    it('shows delete button for cancelled jobs', () => {
      const cancelledJob = { ...baseJob, status: 'cancelled' } as Job
      render(
        <JobActions
          job={cancelledJob}
          onRefresh={mockOnRefresh}
          showLogs={false}
          onToggleLogs={mockOnToggleLogs}
        />
      )

      expect(screen.getByText('Delete')).toBeInTheDocument()
    })

    it('does not show delete button for pending jobs', () => {
      const pendingJob = { ...baseJob, status: 'pending' } as Job
      render(
        <JobActions
          job={pendingJob}
          onRefresh={mockOnRefresh}
          showLogs={false}
          onToggleLogs={mockOnToggleLogs}
        />
      )

      expect(screen.queryByText('Delete')).not.toBeInTheDocument()
    })
  })

  describe('Show Logs button', () => {
    it('always shows Show Logs button', () => {
      const pendingJob = { ...baseJob, status: 'pending' } as Job
      render(
        <JobActions
          job={pendingJob}
          onRefresh={mockOnRefresh}
          showLogs={false}
          onToggleLogs={mockOnToggleLogs}
        />
      )

      expect(screen.getByText('Show Logs')).toBeInTheDocument()
    })

    it('shows Hide Logs when logs are visible', () => {
      const pendingJob = { ...baseJob, status: 'pending' } as Job
      render(
        <JobActions
          job={pendingJob}
          onRefresh={mockOnRefresh}
          showLogs={true}
          onToggleLogs={mockOnToggleLogs}
        />
      )

      expect(screen.getByText('Hide Logs')).toBeInTheDocument()
    })
  })
})
