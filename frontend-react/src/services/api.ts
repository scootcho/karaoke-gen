/**
 * API client service for karaoke generation backend
 */
import axios, { AxiosInstance } from 'axios';
import { Job, JobCreateResponse, HealthResponse } from '../types/job';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080/api';

class ApiService {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  /**
   * Health check
   */
  async health(): Promise<HealthResponse> {
    const response = await this.client.get<HealthResponse>('/health');
    return response.data;
  }

  /**
   * Create job from URL (YouTube, etc.)
   */
  async createJobFromUrl(url: string): Promise<JobCreateResponse> {
    const response = await this.client.post<JobCreateResponse>('/jobs', { url });
    return response.data;
  }

  /**
   * Upload file and create job
   */
  async uploadFile(file: File, artist: string, title: string): Promise<JobCreateResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('artist', artist);
    formData.append('title', title);

    const response = await this.client.post<JobCreateResponse>('/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }

  /**
   * Get job status and details
   */
  async getJob(jobId: string): Promise<Job> {
    const response = await this.client.get<Job>(`/jobs/${jobId}`);
    return response.data;
  }

  /**
   * List all jobs
   */
  async listJobs(): Promise<Job[]> {
    const response = await this.client.get<Job[]>('/jobs');
    return response.data;
  }

  /**
   * Delete job
   */
  async deleteJob(jobId: string, deleteFiles: boolean = true): Promise<void> {
    await this.client.delete(`/jobs/${jobId}`, {
      params: { delete_files: deleteFiles },
    });
  }
}

export const apiService = new ApiService();

