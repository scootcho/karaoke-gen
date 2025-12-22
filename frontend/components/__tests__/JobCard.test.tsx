/**
 * Tests for JobCard component
 */

import { render, screen, fireEvent } from '@testing-library/react'
import { JobCard } from '../job/JobCard'
import { Job } from '@/lib/api'

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
  })

  it('renders job information', () => {
    render(<JobCard job={mockJob} onRefresh={mockOnRefresh} />)
    
    expect(screen.getByText('Test Artist - Test Song')).toBeInTheDocument()
    expect(screen.getByText(/Job ID:/)).toBeInTheDocument()
  })

  it('shows progress bar for processing jobs', () => {
    render(<JobCard job={mockJob} onRefresh={mockOnRefresh} />)
    
    // Expand details
    fireEvent.click(screen.getByText('Test Artist - Test Song'))
    
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
    
    expect(screen.getByText('Select Audio Source')).toBeInTheDocument()
  })

  it('shows instrumental selection button for awaiting_instrumental_selection status', () => {
    const instrumentalJob = { ...mockJob, status: 'awaiting_instrumental_selection' }
    render(<JobCard job={instrumentalJob} onRefresh={mockOnRefresh} />)
    
    // Expand details
    fireEvent.click(screen.getByText('Test Artist - Test Song'))
    
    expect(screen.getByText('Select Instrumental')).toBeInTheDocument()
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

