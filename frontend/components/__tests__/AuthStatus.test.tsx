/**
 * Tests for AuthStatus and AuthDialog components
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { AuthStatus } from '../auth/AuthStatus'
import { AuthDialog } from '../auth/AuthDialog'
import { getAccessToken, setAccessToken, clearAccessToken } from '@/lib/api'

// Mock the api module
jest.mock('@/lib/api', () => ({
  getAccessToken: jest.fn(),
  setAccessToken: jest.fn(),
  clearAccessToken: jest.fn(),
}))

const mockGetAccessToken = getAccessToken as jest.Mock
const mockSetAccessToken = setAccessToken as jest.Mock
const mockClearAccessToken = clearAccessToken as jest.Mock

// Mock window.location.reload
const mockReload = jest.fn()
Object.defineProperty(window, 'location', {
  value: { reload: mockReload },
  writable: true,
})

describe('AuthStatus', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('shows Login button when not authenticated', () => {
    mockGetAccessToken.mockReturnValue(null)
    render(<AuthStatus />)

    expect(screen.getByRole('button', { name: /login/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /logout/i })).not.toBeInTheDocument()
  })

  it('shows Logout button when authenticated', () => {
    mockGetAccessToken.mockReturnValue('test-token')
    render(<AuthStatus />)

    expect(screen.getByRole('button', { name: /logout/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /login/i })).not.toBeInTheDocument()
  })

  it('opens auth dialog when Login is clicked', () => {
    mockGetAccessToken.mockReturnValue(null)
    render(<AuthStatus />)

    fireEvent.click(screen.getByRole('button', { name: /login/i }))

    // Dialog should appear with "Authentication Required" title
    expect(screen.getByText('Authentication Required')).toBeInTheDocument()
  })

  it('clears token and reloads when Logout is clicked', () => {
    mockGetAccessToken.mockReturnValue('test-token')
    render(<AuthStatus />)

    fireEvent.click(screen.getByRole('button', { name: /logout/i }))

    expect(mockClearAccessToken).toHaveBeenCalled()
    expect(mockReload).toHaveBeenCalled()
  })

  it('calls onAuthChange callback when logging out', () => {
    mockGetAccessToken.mockReturnValue('test-token')
    const mockOnAuthChange = jest.fn()
    render(<AuthStatus onAuthChange={mockOnAuthChange} />)

    fireEvent.click(screen.getByRole('button', { name: /logout/i }))

    expect(mockOnAuthChange).toHaveBeenCalled()
  })
})

describe('AuthDialog', () => {
  const mockOnClose = jest.fn()
  const mockOnSuccess = jest.fn()

  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('renders when open is true', () => {
    render(<AuthDialog open={true} onClose={mockOnClose} onSuccess={mockOnSuccess} />)

    expect(screen.getByText('Authentication Required')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Enter access token')).toBeInTheDocument()
  })

  it('does not render when open is false', () => {
    render(<AuthDialog open={false} onClose={mockOnClose} onSuccess={mockOnSuccess} />)

    expect(screen.queryByText('Authentication Required')).not.toBeInTheDocument()
  })

  it('calls onClose when Cancel is clicked', () => {
    render(<AuthDialog open={true} onClose={mockOnClose} onSuccess={mockOnSuccess} />)

    fireEvent.click(screen.getByRole('button', { name: /cancel/i }))

    expect(mockOnClose).toHaveBeenCalled()
  })

  it('disables Authenticate button when token is empty', () => {
    render(<AuthDialog open={true} onClose={mockOnClose} onSuccess={mockOnSuccess} />)

    const authenticateBtn = screen.getByRole('button', { name: /authenticate/i })
    expect(authenticateBtn).toBeDisabled()
  })

  it('enables Authenticate button when token is entered', () => {
    render(<AuthDialog open={true} onClose={mockOnClose} onSuccess={mockOnSuccess} />)

    const input = screen.getByPlaceholderText('Enter access token')
    fireEvent.change(input, { target: { value: 'my-token' } })

    const authenticateBtn = screen.getByRole('button', { name: /authenticate/i })
    expect(authenticateBtn).not.toBeDisabled()
  })

  it('sets token and calls onSuccess when form is submitted', async () => {
    render(<AuthDialog open={true} onClose={mockOnClose} onSuccess={mockOnSuccess} />)

    const input = screen.getByPlaceholderText('Enter access token')
    fireEvent.change(input, { target: { value: 'my-token' } })

    const authenticateBtn = screen.getByRole('button', { name: /authenticate/i })
    fireEvent.click(authenticateBtn)

    expect(mockSetAccessToken).toHaveBeenCalledWith('my-token')
    expect(mockOnSuccess).toHaveBeenCalled()
  })

  it('trims whitespace from token', () => {
    render(<AuthDialog open={true} onClose={mockOnClose} onSuccess={mockOnSuccess} />)

    const input = screen.getByPlaceholderText('Enter access token')
    fireEvent.change(input, { target: { value: '  my-token  ' } })

    const authenticateBtn = screen.getByRole('button', { name: /authenticate/i })
    fireEvent.click(authenticateBtn)

    expect(mockSetAccessToken).toHaveBeenCalledWith('my-token')
  })

  it('shows error for empty token submission', () => {
    render(<AuthDialog open={true} onClose={mockOnClose} onSuccess={mockOnSuccess} />)

    // Token with only whitespace
    const input = screen.getByPlaceholderText('Enter access token')
    fireEvent.change(input, { target: { value: '   ' } })

    // Button should still be disabled for whitespace-only input
    const authenticateBtn = screen.getByRole('button', { name: /authenticate/i })
    expect(authenticateBtn).toBeDisabled()
  })
})
