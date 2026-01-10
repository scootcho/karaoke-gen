import { test, expect } from '@playwright/test';
import { setupApiFixtures, setAuthToken, clearAuthToken } from '../fixtures/test-helper';

/**
 * Admin Job Detail Page Tests
 *
 * Tests the admin job detail page functionality with mocked API responses.
 * These tests run as part of the regression suite on every PR.
 */

// Mock data for tests
const mockAdminUser = {
  user: {
    email: 'admin@nomadkaraoke.com',
    role: 'admin',
    credits: 100,
    is_active: true,
  },
};

const mockJob = {
  job_id: 'test-job-123',
  status: 'complete',
  progress: 100,
  artist: 'Test Artist',
  title: 'Test Song',
  user_email: 'user@example.com',
  created_at: '2026-01-09T10:00:00Z',
  updated_at: '2026-01-09T10:30:00Z',
  url: 'https://youtube.com/watch?v=abc123',
  theme_id: 'nomad',
  enable_cdg: false,
  enable_txt: false,
  enable_youtube_upload: true,
  timeline: [
    { status: 'pending', timestamp: '2026-01-09T10:00:00Z', progress: 0 },
    { status: 'downloading', timestamp: '2026-01-09T10:01:00Z', progress: 10 },
    { status: 'separating_stage1', timestamp: '2026-01-09T10:05:00Z', progress: 30 },
    { status: 'complete', timestamp: '2026-01-09T10:30:00Z', progress: 100 },
  ],
  state_data: {
    youtube_url: 'https://youtube.com/watch?v=xyz789',
    dropbox_link: 'https://dropbox.com/s/abc123',
  },
  file_urls: {
    input: 'gs://bucket/jobs/test-job-123/input.flac',
    stems: {
      instrumental_clean: 'gs://bucket/jobs/test-job-123/stems/clean.flac',
    },
  },
  request_metadata: {
    environment: 'production',
    client_ip: '192.168.1.1',
    user_agent: 'Mozilla/5.0',
    server_version: '0.72.0',
  },
};

const mockJobsList = [mockJob];

// Note: API returns { logs: [...] }, not just the array
const mockLogs = {
  logs: [
    { timestamp: '2026-01-09T10:01:00Z', level: 'INFO', worker: 'audio', message: 'Starting audio download' },
    { timestamp: '2026-01-09T10:05:00Z', level: 'INFO', worker: 'audio', message: 'Audio download complete' },
    { timestamp: '2026-01-09T10:10:00Z', level: 'WARNING', worker: 'lyrics', message: 'Retrying transcription' },
    { timestamp: '2026-01-09T10:30:00Z', level: 'INFO', worker: 'video', message: 'Video encoding complete' },
  ],
};

// Mock files response with signed URLs
const mockFiles = {
  job_id: 'test-job-123',
  artist: 'Test Artist',
  title: 'Test Song',
  files: [
    {
      name: 'input.flac',
      path: 'gs://bucket/jobs/test-job-123/input.flac',
      download_url: 'https://storage.googleapis.com/signed/input.flac',
      category: '',
      file_key: 'input',
    },
    {
      name: 'instrumental_clean.flac',
      path: 'gs://bucket/jobs/test-job-123/stems/instrumental_clean.flac',
      download_url: 'https://storage.googleapis.com/signed/instrumental_clean.flac',
      category: 'stems',
      file_key: 'instrumental_clean',
    },
    {
      name: 'vocals.flac',
      path: 'gs://bucket/jobs/test-job-123/stems/vocals.flac',
      download_url: 'https://storage.googleapis.com/signed/vocals.flac',
      category: 'stems',
      file_key: 'vocals',
    },
    {
      name: 'output.lrc',
      path: 'gs://bucket/jobs/test-job-123/lyrics/output.lrc',
      download_url: 'https://storage.googleapis.com/signed/output.lrc',
      category: 'lyrics',
      file_key: 'lrc',
    },
    {
      name: 'video_720p.mp4',
      path: 'gs://bucket/jobs/test-job-123/finals/video_720p.mp4',
      download_url: 'https://storage.googleapis.com/signed/video_720p.mp4',
      category: 'finals',
      file_key: 'lossy_720p_mp4',
    },
  ],
  total_files: 5,
};

test.describe('Admin Job Detail Page', () => {
  test.beforeEach(async ({ page }) => {
    // Set admin auth token
    await setAuthToken(page, 'mock-admin-token');
  });

  test('navigates from jobs list to detail page', async ({ page }) => {
    // Set up API mocks
    await setupApiFixtures(page, {
      mocks: [
        { method: 'GET', path: '/api/users/me', response: { body: mockAdminUser } },
        { method: 'GET', path: '/api/jobs', response: { body: mockJobsList } },
        { method: 'GET', path: '/api/jobs/test-job-123', response: { body: mockJob } },
        { method: 'GET', path: '/api/jobs/test-job-123/logs', response: { body: mockLogs } },
      ],
    });

    // Go to jobs list
    await page.goto('/admin/jobs');
    await page.waitForLoadState('networkidle');

    // Click on the job row (the job ID text)
    await page.click('text=test-job-123');

    // Should navigate to detail page (using query param)
    // Note: Next.js may add trailing slash depending on config
    await expect(page).toHaveURL(/\/admin\/jobs\/?\?id=test-job-123/);

    // Job header should be visible
    await expect(page.getByText('Job test-job-123')).toBeVisible();
    await expect(page.getByText('Test Artist - Test Song')).toBeVisible();
  });

  test('displays job metadata sections', async ({ page }) => {
    await setupApiFixtures(page, {
      mocks: [
        { method: 'GET', path: '/api/users/me', response: { body: mockAdminUser } },
        { method: 'GET', path: '/api/jobs', response: { body: [] } }, // List endpoint is called on page load
        { method: 'GET', path: '/api/jobs/test-job-123', response: { body: mockJob } },
        { method: 'GET', path: '/api/jobs/test-job-123/logs', response: { body: mockLogs } },
      ],
    });

    await page.goto('/admin/jobs?id=test-job-123');
    await page.waitForLoadState('networkidle');

    // Overview cards should show
    await expect(page.getByText('user@example.com')).toBeVisible();
    await expect(page.getByText('YouTube URL')).toBeVisible();
    await expect(page.getByText('100%')).toBeVisible();

    // Timeline section should be visible (expanded by default)
    await expect(page.getByText('Timeline (4 events)')).toBeVisible();
    // Check for specific timeline entries - use first() to avoid strict mode violations
    await expect(page.getByText('pending').first()).toBeVisible();
    // 'complete' appears in multiple places (status badge, timeline, logs), check timeline header exists
    await expect(page.locator('[data-slot="badge"]').filter({ hasText: 'complete' }).first()).toBeVisible();

    // Worker logs section should be visible
    await expect(page.getByText('Worker Logs (4 entries)')).toBeVisible();
  });

  test('displays timeline with stage durations', async ({ page }) => {
    await setupApiFixtures(page, {
      mocks: [
        { method: 'GET', path: '/api/users/me', response: { body: mockAdminUser } },
        { method: 'GET', path: '/api/jobs', response: { body: [] } },
        { method: 'GET', path: '/api/jobs/test-job-123', response: { body: mockJob } },
        { method: 'GET', path: '/api/jobs/test-job-123/logs', response: { body: mockLogs } },
      ],
    });

    await page.goto('/admin/jobs?id=test-job-123');
    await page.waitForLoadState('networkidle');

    // Timeline should show durations
    // pending -> downloading took 1 minute
    await expect(page.getByText(/1m 0s/)).toBeVisible();
  });

  test('displays request metadata when available', async ({ page }) => {
    await setupApiFixtures(page, {
      mocks: [
        { method: 'GET', path: '/api/users/me', response: { body: mockAdminUser } },
        { method: 'GET', path: '/api/jobs', response: { body: [] } },
        { method: 'GET', path: '/api/jobs/test-job-123', response: { body: mockJob } },
        { method: 'GET', path: '/api/jobs/test-job-123/logs', response: { body: mockLogs } },
      ],
    });

    await page.goto('/admin/jobs?id=test-job-123');
    await page.waitForLoadState('networkidle');

    // Click to expand Request Metadata section
    await page.click('text=Request Metadata');

    // Should show metadata values
    await expect(page.getByText('production')).toBeVisible();
    await expect(page.getByText('192.168.1.1')).toBeVisible();
  });

  test('shows error message for failed jobs', async ({ page }) => {
    const failedJob = {
      ...mockJob,
      status: 'failed',
      progress: 45,
      error_message: 'Audio separation timed out after 10 minutes',
      error_details: { worker: 'audio', timeout_seconds: 600 },
    };

    await setupApiFixtures(page, {
      mocks: [
        { method: 'GET', path: '/api/users/me', response: { body: mockAdminUser } },
        { method: 'GET', path: '/api/jobs', response: { body: [] } },
        { method: 'GET', path: '/api/jobs/test-job-123', response: { body: failedJob } },
        { method: 'GET', path: '/api/jobs/test-job-123/logs', response: { body: mockLogs } },
      ],
    });

    await page.goto('/admin/jobs?id=test-job-123');
    await page.waitForLoadState('networkidle');

    // Error card should be visible
    await expect(page.getByText('Error')).toBeVisible();
    await expect(page.getByText('Audio separation timed out after 10 minutes')).toBeVisible();
  });

  test('back button returns to jobs list', async ({ page }) => {
    await setupApiFixtures(page, {
      mocks: [
        { method: 'GET', path: '/api/users/me', response: { body: mockAdminUser } },
        { method: 'GET', path: '/api/jobs/test-job-123', response: { body: mockJob } },
        { method: 'GET', path: '/api/jobs/test-job-123/logs', response: { body: mockLogs } },
        { method: 'GET', path: '/api/jobs', response: { body: mockJobsList } },
      ],
    });

    await page.goto('/admin/jobs?id=test-job-123');
    await page.waitForLoadState('networkidle');

    // Click back button (ghost button with ArrowLeft icon)
    await page.locator('button:has(svg.lucide-arrow-left)').click();

    // Should navigate to jobs list (no query param)
    // Note: Next.js may add trailing slash depending on config
    await expect(page).toHaveURL(/\/admin\/jobs\/?$/);
  });

  test('handles job not found gracefully', async ({ page }) => {
    await setupApiFixtures(page, {
      mocks: [
        { method: 'GET', path: '/api/users/me', response: { body: mockAdminUser } },
        { method: 'GET', path: '/api/jobs', response: { body: [] } },
        { method: 'GET', path: '/api/jobs/nonexistent', response: { status: 404, body: { detail: 'Job not found' } } },
        { method: 'GET', path: '/api/jobs/nonexistent/logs', response: { body: { logs: [] } } },
      ],
    });

    await page.goto('/admin/jobs?id=nonexistent');
    await page.waitForLoadState('networkidle');

    // Should show not found message
    await expect(page.getByText('Job not found')).toBeVisible();
    await expect(page.getByRole('button', { name: /Back to Jobs/i })).toBeVisible();
  });

  test('delete job shows confirmation dialog', async ({ page }) => {
    await setupApiFixtures(page, {
      mocks: [
        { method: 'GET', path: '/api/users/me', response: { body: mockAdminUser } },
        { method: 'GET', path: '/api/jobs', response: { body: [] } },
        { method: 'GET', path: '/api/jobs/test-job-123', response: { body: mockJob } },
        { method: 'GET', path: '/api/jobs/test-job-123/logs', response: { body: mockLogs } },
      ],
    });

    await page.goto('/admin/jobs?id=test-job-123');
    await page.waitForLoadState('networkidle');

    // Click delete button
    await page.click('button:has-text("Delete")');

    // Confirmation dialog should appear
    await expect(page.getByRole('alertdialog')).toBeVisible();
    // The dialog text includes "job test-job-123" (not the exact string from before)
    await expect(page.getByText(/delete job test-job-123/i)).toBeVisible();

    // Cancel button should close dialog
    await page.click('button:has-text("Cancel")');
    await expect(page.getByRole('alertdialog')).not.toBeVisible();
  });

  test('refresh button reloads job data', async ({ page }) => {
    // Set up API mocks
    await setupApiFixtures(page, {
      mocks: [
        { method: 'GET', path: '/api/users/me', response: { body: mockAdminUser } },
        { method: 'GET', path: '/api/jobs', response: { body: [] } },
        { method: 'GET', path: '/api/jobs/test-job-123', response: { body: mockJob } },
        { method: 'GET', path: '/api/jobs/test-job-123/logs', response: { body: mockLogs } },
      ],
    });

    await page.goto('/admin/jobs?id=test-job-123');
    await page.waitForLoadState('networkidle');

    // Verify initial page loaded correctly
    await expect(page.getByText('Job test-job-123')).toBeVisible();

    // Click refresh button
    await page.click('button:has-text("Refresh")');

    // Wait for refresh to complete - the button shows a spinner while loading
    await page.waitForLoadState('networkidle');

    // Verify the job data is still visible (refresh completed successfully)
    await expect(page.getByText('Job test-job-123')).toBeVisible();
    await expect(page.getByText('Test Artist - Test Song')).toBeVisible();
  });

  test('files section shows downloadable files grouped by category', async ({ page }) => {
    await setupApiFixtures(page, {
      mocks: [
        { method: 'GET', path: '/api/users/me', response: { body: mockAdminUser } },
        { method: 'GET', path: '/api/jobs', response: { body: [] } },
        { method: 'GET', path: '/api/jobs/test-job-123', response: { body: mockJob } },
        { method: 'GET', path: '/api/jobs/test-job-123/logs', response: { body: mockLogs } },
        { method: 'GET', path: '/api/admin/jobs/test-job-123/files', response: { body: mockFiles } },
      ],
    });

    await page.goto('/admin/jobs?id=test-job-123');
    await page.waitForLoadState('networkidle');

    // Expand the Files accordion
    await page.click('text=Files (5 downloadable)');

    // Should show category groups (use heading role to be specific, avoid matching log entries)
    await expect(page.getByRole('heading', { name: 'Audio Stems' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Lyrics' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Final Outputs' })).toBeVisible();

    // Should show individual files
    await expect(page.getByText('input.flac')).toBeVisible();
    await expect(page.getByText('instrumental_clean.flac')).toBeVisible();
    await expect(page.getByText('output.lrc')).toBeVisible();

    // Should show download buttons with correct links
    const downloadLinks = page.locator('a[href*="storage.googleapis.com/signed"]');
    await expect(downloadLinks).toHaveCount(5);
  });

  test('files section handles empty files gracefully', async ({ page }) => {
    const emptyFiles = {
      job_id: 'test-job-123',
      artist: 'Test Artist',
      title: 'Test Song',
      files: [],
      total_files: 0,
    };

    await setupApiFixtures(page, {
      mocks: [
        { method: 'GET', path: '/api/users/me', response: { body: mockAdminUser } },
        { method: 'GET', path: '/api/jobs', response: { body: [] } },
        { method: 'GET', path: '/api/jobs/test-job-123', response: { body: mockJob } },
        { method: 'GET', path: '/api/jobs/test-job-123/logs', response: { body: mockLogs } },
        { method: 'GET', path: '/api/admin/jobs/test-job-123/files', response: { body: emptyFiles } },
      ],
    });

    await page.goto('/admin/jobs?id=test-job-123');
    await page.waitForLoadState('networkidle');

    // Expand the Files accordion
    await page.click('text=Files (0 downloadable)');

    // Should show "no files" message
    await expect(page.getByText('No files available')).toBeVisible();
  });

  test('admin actions section shows reset options', async ({ page }) => {
    await setupApiFixtures(page, {
      mocks: [
        { method: 'GET', path: '/api/users/me', response: { body: mockAdminUser } },
        { method: 'GET', path: '/api/jobs', response: { body: [] } },
        { method: 'GET', path: '/api/jobs/test-job-123', response: { body: mockJob } },
        { method: 'GET', path: '/api/jobs/test-job-123/logs', response: { body: mockLogs } },
      ],
    });

    await page.goto('/admin/jobs?id=test-job-123');
    await page.waitForLoadState('networkidle');

    // Expand the Admin Actions accordion
    await page.click('text=Admin Actions');

    // Should show reset options
    await expect(page.getByText('Reset Job State')).toBeVisible();
    // Check the reset buttons are visible - use .first() to handle multiple matches
    await expect(page.locator('button:has-text("Pending")').first()).toBeVisible();
    await expect(page.locator('button:has-text("Audio Selection")').first()).toBeVisible();
    await expect(page.locator('button:has-text("Lyrics Review")').first()).toBeVisible();
    await expect(page.locator('button:has-text("Instrumental Selection")').first()).toBeVisible();
  });

  test('clicking reset button shows confirmation dialog', async ({ page }) => {
    await setupApiFixtures(page, {
      mocks: [
        { method: 'GET', path: '/api/users/me', response: { body: mockAdminUser } },
        { method: 'GET', path: '/api/jobs', response: { body: [] } },
        { method: 'GET', path: '/api/jobs/test-job-123', response: { body: mockJob } },
        { method: 'GET', path: '/api/jobs/test-job-123/logs', response: { body: mockLogs } },
      ],
    });

    await page.goto('/admin/jobs?id=test-job-123');
    await page.waitForLoadState('networkidle');

    // Expand the Admin Actions accordion
    await page.click('text=Admin Actions');

    // Click a reset button (Pending)
    await page.locator('button:has-text("Pending")').click();

    // Should show confirmation dialog
    await expect(page.getByRole('alertdialog')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Reset Job' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Cancel' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Reset' })).toBeVisible();
  });
});
