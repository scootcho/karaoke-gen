/**
 * Job status hook using TanStack Query with polling
 */
import { useQuery, UseQueryResult } from '@tanstack/react-query';
import { apiService } from '../services/api';
import { Job, JobStatus } from '../types/job';

export function useJobStatus(jobId: string | null, enabled: boolean = true): UseQueryResult<Job, Error> {
  return useQuery({
    queryKey: ['job', jobId],
    queryFn: () => apiService.getJob(jobId!),
    enabled: enabled && !!jobId,
    refetchInterval: (data) => {
      // Poll every 3 seconds if job is in progress
      if (data?.status === JobStatus.PROCESSING || 
          data?.status === JobStatus.QUEUED ||
          data?.status === JobStatus.FINALIZING) {
        return 3000;
      }
      return false;
    },
  });
}

export function useJobsList(): UseQueryResult<Job[], Error> {
  return useQuery({
    queryKey: ['jobs'],
    queryFn: () => apiService.listJobs(),
    refetchInterval: 10000, // Poll every 10 seconds
  });
}

