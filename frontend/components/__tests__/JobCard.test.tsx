/**
 * Tests for JobCard component
 */

import { render, screen, fireEvent } from '@testing-library/react'
import { JobCard } from '../job/JobCard'
import { Job } from '@/lib/api'
import { useAutoMode } from '@/lib/auto-mode'

// Mock the auto-mode hook
jest.mock('@/lib/auto-mode', () => ({
  useAutoMode: jest.fn()
}))

const mockUseAutoMode = useAutoMode as jest.Mock

// Mock the child components
jest.mock('../job/JobActions', () => ({
  JobActions: () => <div data-testid="job-actions">Job Actions</div>
}))

jest.mock('../job/JobLogs', () => ({
  JobLogs: () => <div data-testid="job-logs">Job Logs</div>
}))

jest.mock('../job/OutputLinks', () => ({
  OutputLinks: () => <div data-testid="output-links">Output Links</div>
}))

jest.mock('../job/InstrumentalSelector', () => ({
  InstrumentalSelector: () => <div data-testid="instrumental-selector">Instrumental Selector</div>
}))

jest.mock('../audio-search/AudioSearchDialog', () => ({
  AudioSearchDialog: () => <div data-testid="audio-search-dialog">Audio Search Dialog</div>
}))

describe('JobCard', () => {
  const mockOnRefresh = jest.fn()

  const mockJob: Job = {
    job_id: '123',
    status: 'processing',
    progress: 50,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
    artist: 'Test Artist',
    title: 'Test Song',
  }

  beforeEach(() => {
    jest.clearAllMocks()
    // Default mock: auto-mode disabled
    mockUseAutoMode.mockReturnValue({
      enabled: false,
      isProcessing: jest.fn().mockReturnValue(false)
    })
  })

  it('renders job information', () => {
    render(<JobCard job={mockJob} onRefresh={mockOnRefresh} />)

    expect(screen.getByText('Test Artist - Test Song')).toBeInTheDocument()
  })

  it('shows job ID in expanded details', () => {
    render(<JobCard job={mockJob} onRefresh={mockOnRefresh} />)

    // Expand details
    fireEvent.click(screen.getByText('Test Artist - Test Song'))

    expect(screen.getByText(/Job ID:/)).toBeInTheDocument()
    expect(screen.getByText('123')).toBeInTheDocument()
  })

  it('shows progress bar for processing jobs', () => {
    render(<JobCard job={mockJob} onRefresh={mockOnRefresh} />)

    const progressBar = document.querySelector('[style*="width: 50%"]')
    expect(progressBar).toBeInTheDocument()
  })

  it('shows error message for failed jobs', () => {
    const failedJob = { ...mockJob, status: 'failed', error_message: 'Something went wrong' }
    render(<JobCard job={failedJob} onRefresh={mockOnRefresh} />)

    // Expand details
    fireEvent.click(screen.getByText('Test Artist - Test Song'))

    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
  })

  describe('when auto-mode is disabled', () => {
    beforeEach(() => {
      mockUseAutoMode.mockReturnValue({
        enabled: false,
        isProcessing: jest.fn().mockReturnValue(false)
      })
    })

    it('shows lyrics review button for awaiting_review status', () => {
      const reviewJob = { ...mockJob, status: 'awaiting_review' }
      render(<JobCard job={reviewJob} onRefresh={mockOnRefresh} />)

      // Expand details
      fireEvent.click(screen.getByText('Test Artist - Test Song'))

      const reviewLink = screen.getByText('Review Lyrics')
      expect(reviewLink).toBeInTheDocument()
      expect(reviewLink.closest('a')).toHaveAttribute('href', expect.stringContaining('lyrics.nomadkaraoke.com'))
    })

    it('shows audio search button for awaiting_audio_selection status', () => {
      const audioSelectionJob = { ...mockJob, status: 'awaiting_audio_selection' }
      render(<JobCard job={audioSelectionJob} onRefresh={mockOnRefresh} />)

      // Expand details
      fireEvent.click(screen.getByText('Test Artist - Test Song'))

      expect(screen.getByRole('button', { name: 'Select Audio Source' })).toBeInTheDocument()
    })

    it('shows instrumental selection button for awaiting_instrumental_selection status', () => {
      const instrumentalJob = { ...mockJob, status: 'awaiting_instrumental_selection' }
      render(<JobCard job={instrumentalJob} onRefresh={mockOnRefresh} />)

      // Expand details
      fireEvent.click(screen.getByText('Test Artist - Test Song'))

      expect(screen.getByRole('button', { name: 'Select Instrumental' })).toBeInTheDocument()
    })
  })

  describe('when auto-mode is enabled', () => {
    beforeEach(() => {
      mockUseAutoMode.mockReturnValue({
        enabled: true,
        isProcessing: jest.fn().mockReturnValue(false)
      })
    })

    it('shows auto-accept message for awaiting_review status', () => {
      const reviewJob = { ...mockJob, status: 'awaiting_review' }
      render(<JobCard job={reviewJob} onRefresh={mockOnRefresh} />)

      // Expand details
      fireEvent.click(screen.getByText('Test Artist - Test Song'))

      expect(screen.getByText(/Will auto-accept/)).toBeInTheDocument()
      expect(screen.queryByText('Review Lyrics')).not.toBeInTheDocument()
    })

    it('shows auto-select message for awaiting_instrumental_selection status', () => {
      const instrumentalJob = { ...mockJob, status: 'awaiting_instrumental_selection' }
      render(<JobCard job={instrumentalJob} onRefresh={mockOnRefresh} />)

      // Expand details
      fireEvent.click(screen.getByText('Test Artist - Test Song'))

      expect(screen.getByText(/Will auto-select clean/)).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Select Instrumental' })).not.toBeInTheDocument()
    })

    it('shows auto-select message for awaiting_audio_selection status', () => {
      const audioJob = { ...mockJob, status: 'awaiting_audio_selection' }
      render(<JobCard job={audioJob} onRefresh={mockOnRefresh} />)

      // Expand details
      fireEvent.click(screen.getByText('Test Artist - Test Song'))

      expect(screen.getByText(/Will auto-select first/)).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Select Audio Source' })).not.toBeInTheDocument()
    })

    it('shows auto-processing indicator when processing', () => {
      mockUseAutoMode.mockReturnValue({
        enabled: true,
        isProcessing: jest.fn().mockReturnValue(true)
      })

      const reviewJob = { ...mockJob, status: 'awaiting_review' }
      render(<JobCard job={reviewJob} onRefresh={mockOnRefresh} />)

      // Expand details
      fireEvent.click(screen.getByText('Test Artist - Test Song'))

      expect(screen.getByText(/Auto-processing.../)).toBeInTheDocument()
    })
  })

  it('shows output links for complete jobs', () => {
    const completeJob = { ...mockJob, status: 'complete' }
    render(<JobCard job={completeJob} onRefresh={mockOnRefresh} />)

    // Expand details
    fireEvent.click(screen.getByText('Test Artist - Test Song'))

    expect(screen.getByTestId('output-links')).toBeInTheDocument()
  })

  it('toggles details on click', () => {
    render(<JobCard job={mockJob} onRefresh={mockOnRefresh} />)

    // Should not show actions initially
    expect(screen.queryByTestId('job-actions')).not.toBeInTheDocument()

    // Click to expand
    fireEvent.click(screen.getByText('Test Artist - Test Song'))

    // Should show actions now
    expect(screen.getByTestId('job-actions')).toBeInTheDocument()

    // Click to collapse
    fireEvent.click(screen.getByText('Test Artist - Test Song'))

    // Should hide actions again
    expect(screen.queryByTestId('job-actions')).not.toBeInTheDocument()
  })
})
