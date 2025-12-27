/**
 * Tests for JobCard component
 *
 * Note: Job cards are no longer collapsible - details are always visible
 */

import { render, screen } from '@testing-library/react'
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

  it('shows job ID (details always visible)', () => {
    render(<JobCard job={mockJob} onRefresh={mockOnRefresh} />)

    // Details are always visible now (no need to click to expand)
    expect(screen.getByText(/Job ID:/)).toBeInTheDocument()
    expect(screen.getByText('123')).toBeInTheDocument()
  })

  it('shows job actions (details always visible)', () => {
    render(<JobCard job={mockJob} onRefresh={mockOnRefresh} />)

    // Actions should be immediately visible
    expect(screen.getByTestId('job-actions')).toBeInTheDocument()
  })

  it('shows progress bar for processing jobs', () => {
    render(<JobCard job={mockJob} onRefresh={mockOnRefresh} />)

    const progressBar = document.querySelector('[style*="width: 50%"]')
    expect(progressBar).toBeInTheDocument()
  })

  it('does not show progress bar when progress is 0', () => {
    const noProgressJob = { ...mockJob, progress: 0 }
    render(<JobCard job={noProgressJob} onRefresh={mockOnRefresh} />)

    const progressBar = document.querySelector('[style*="width: 0%"]')
    expect(progressBar).not.toBeInTheDocument()
  })

  it('does not show progress bar when job is complete', () => {
    const completeJob = { ...mockJob, status: 'complete', progress: 100 }
    render(<JobCard job={completeJob} onRefresh={mockOnRefresh} />)

    const progressBar = document.querySelector('[class*="bg-amber-500"]')
    expect(progressBar).not.toBeInTheDocument()
  })

  it('shows error message for failed jobs', () => {
    const failedJob = { ...mockJob, status: 'failed', error_message: 'Something went wrong' }
    render(<JobCard job={failedJob} onRefresh={mockOnRefresh} />)

    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
  })

  it('applies orange border for interactive jobs', () => {
    const interactiveJob = { ...mockJob, status: 'awaiting_review' }
    const { container } = render(<JobCard job={interactiveJob} onRefresh={mockOnRefresh} />)

    const card = container.firstChild
    expect(card).toHaveClass('border-orange-500/50')
  })

  it('applies green border for complete jobs', () => {
    const completeJob = { ...mockJob, status: 'complete' }
    const { container } = render(<JobCard job={completeJob} onRefresh={mockOnRefresh} />)

    const card = container.firstChild
    expect(card).toHaveClass('border-green-500/30')
  })

  it('applies red border for failed jobs', () => {
    const failedJob = { ...mockJob, status: 'failed' }
    const { container } = render(<JobCard job={failedJob} onRefresh={mockOnRefresh} />)

    const card = container.firstChild
    expect(card).toHaveClass('border-red-500/30')
  })

  describe('when auto-mode is disabled', () => {
    beforeEach(() => {
      mockUseAutoMode.mockReturnValue({
        enabled: false,
        isProcessing: jest.fn().mockReturnValue(false)
      })
    })

    it('shows lyrics review link for awaiting_review status', () => {
      const reviewJob = { ...mockJob, status: 'awaiting_review', review_token: 'test-token-123' }
      render(<JobCard job={reviewJob} onRefresh={mockOnRefresh} />)

      const reviewLink = screen.getByText('Review Lyrics')
      expect(reviewLink).toBeInTheDocument()
      const href = reviewLink.closest('a')?.getAttribute('href') || ''
      expect(href).toContain('gen.nomadkaraoke.com/lyrics')
      expect(href).toContain('baseApiUrl=')
      expect(href).toContain('reviewToken=test-token-123')
    })

    it('shows audio search button for awaiting_audio_selection status', () => {
      const audioSelectionJob = { ...mockJob, status: 'awaiting_audio_selection' }
      render(<JobCard job={audioSelectionJob} onRefresh={mockOnRefresh} />)

      expect(screen.getByRole('button', { name: 'Select Audio Source' })).toBeInTheDocument()
    })

    it('shows instrumental selection button for awaiting_instrumental_selection status', () => {
      const instrumentalJob = { ...mockJob, status: 'awaiting_instrumental_selection' }
      render(<JobCard job={instrumentalJob} onRefresh={mockOnRefresh} />)

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

      expect(screen.getByText(/Will auto-accept/)).toBeInTheDocument()
      expect(screen.queryByText('Review Lyrics')).not.toBeInTheDocument()
    })

    it('shows auto-select message for awaiting_instrumental_selection status', () => {
      const instrumentalJob = { ...mockJob, status: 'awaiting_instrumental_selection' }
      render(<JobCard job={instrumentalJob} onRefresh={mockOnRefresh} />)

      expect(screen.getByText(/Will auto-select clean/)).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Select Instrumental' })).not.toBeInTheDocument()
    })

    it('shows auto-select message for awaiting_audio_selection status', () => {
      const audioJob = { ...mockJob, status: 'awaiting_audio_selection' }
      render(<JobCard job={audioJob} onRefresh={mockOnRefresh} />)

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

      expect(screen.getByText(/Auto-processing.../)).toBeInTheDocument()
    })
  })

  it('shows output links for complete jobs', () => {
    const completeJob = { ...mockJob, status: 'complete' }
    render(<JobCard job={completeJob} onRefresh={mockOnRefresh} />)

    expect(screen.getByTestId('output-links')).toBeInTheDocument()
  })

  it('handles unknown artist gracefully', () => {
    const noArtistJob = { ...mockJob, artist: undefined }
    render(<JobCard job={noArtistJob} onRefresh={mockOnRefresh} />)

    expect(screen.getByText('Unknown - Test Song')).toBeInTheDocument()
  })

  it('handles unknown title gracefully', () => {
    const noTitleJob = { ...mockJob, title: undefined }
    render(<JobCard job={noTitleJob} onRefresh={mockOnRefresh} />)

    expect(screen.getByText('Test Artist - Unknown')).toBeInTheDocument()
  })
})
