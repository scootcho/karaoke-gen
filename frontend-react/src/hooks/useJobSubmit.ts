/**
 * Job submission hook using TanStack Query
 */
import { useMutation, UseMutationResult } from '@tanstack/react-query';
import { apiService } from '../services/api';
import { JobCreateResponse } from '../types/job';

interface SubmitFromUrlParams {
  url: string;
}

interface SubmitFromUploadParams {
  file: File;
  artist: string;
  title: string;
}

export function useSubmitJobFromUrl(): UseMutationResult<JobCreateResponse, Error, SubmitFromUrlParams> {
  return useMutation({
    mutationFn: ({ url }: SubmitFromUrlParams) => apiService.createJobFromUrl(url),
  });
}

export function useSubmitJobFromUpload(): UseMutationResult<JobCreateResponse, Error, SubmitFromUploadParams> {
  return useMutation({
    mutationFn: ({ file, artist, title }: SubmitFromUploadParams) => 
      apiService.uploadFile(file, artist, title),
  });
}

