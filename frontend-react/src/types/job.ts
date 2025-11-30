/**
 * Job TypeScript types
 */

export enum JobStatus {
  QUEUED = 'queued',
  PROCESSING = 'processing',
  AWAITING_REVIEW = 'awaiting_review',
  READY_FOR_FINALIZATION = 'ready_for_finalization',
  FINALIZING = 'finalizing',
  COMPLETE = 'complete',
  ERROR = 'error',
}

export interface TimelineEvent {
  status: string;
  timestamp: string;
  progress?: number;
  message?: string;
}

export interface Job {
  job_id: string;
  status: JobStatus;
  progress: number;
  created_at: string;
  updated_at: string;
  url?: string;
  artist?: string;
  title?: string;
  filename?: string;
  track_output_dir?: string;
  audio_hash?: string;
  timeline: TimelineEvent[];
  output_files: Record<string, string>;
  download_urls: Record<string, string>;
  error_message?: string;
}

export interface JobCreateResponse {
  status: string;
  job_id: string;
  message: string;
}

export interface HealthResponse {
  status: string;
  service: string;
}

