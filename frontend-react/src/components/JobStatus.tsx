/**
 * Job status display component with progress tracking
 */
import React from 'react';
import { useJobStatus } from '../hooks/useJobStatus';
import { JobStatus as JobStatusEnum } from '../types/job';
import { useAppStore } from '../stores/appStore';

export const JobStatus: React.FC = () => {
  const currentJobId = useAppStore((state) => state.currentJobId);
  const { data: job, isLoading, isError, error } = useJobStatus(currentJobId, !!currentJobId);

  if (!currentJobId) {
    return null;
  }

  if (isLoading) {
    return (
      <div className="w-full max-w-2xl mx-auto p-6 bg-white rounded-lg shadow-lg">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-1/4 mb-4"></div>
          <div className="h-8 bg-gray-200 rounded w-full"></div>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="w-full max-w-2xl mx-auto p-6 bg-white rounded-lg shadow-lg">
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <h3 className="text-red-800 font-medium mb-2">Error Loading Job</h3>
          <p className="text-red-600 text-sm">{error.message}</p>
        </div>
      </div>
    );
  }

  if (!job) {
    return null;
  }

  const getStatusColor = (status: JobStatusEnum) => {
    switch (status) {
      case JobStatusEnum.QUEUED:
        return 'bg-gray-500';
      case JobStatusEnum.PROCESSING:
      case JobStatusEnum.FINALIZING:
        return 'bg-blue-500';
      case JobStatusEnum.COMPLETE:
        return 'bg-green-500';
      case JobStatusEnum.ERROR:
        return 'bg-red-500';
      default:
        return 'bg-gray-500';
    }
  };

  const getStatusText = (status: JobStatusEnum) => {
    switch (status) {
      case JobStatusEnum.QUEUED:
        return 'Queued';
      case JobStatusEnum.PROCESSING:
        return 'Processing';
      case JobStatusEnum.FINALIZING:
        return 'Finalizing';
      case JobStatusEnum.COMPLETE:
        return 'Complete';
      case JobStatusEnum.ERROR:
        return 'Error';
      default:
        return status;
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto p-6 bg-white rounded-lg shadow-lg mt-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xl font-bold text-gray-800">
          Job Status: {job.job_id}
        </h3>
        <span
          className={`px-3 py-1 rounded-full text-white text-sm font-medium ${getStatusColor(
            job.status
          )}`}
        >
          {getStatusText(job.status)}
        </span>
      </div>

      {/* Progress Bar */}
      {(job.status === JobStatusEnum.PROCESSING || job.status === JobStatusEnum.FINALIZING) && (
        <div className="mb-4">
          <div className="flex justify-between text-sm text-gray-600 mb-2">
            <span>Progress</span>
            <span>{job.progress}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${job.progress}%` }}
            ></div>
          </div>
        </div>
      )}

      {/* Job Details */}
      <div className="space-y-2 text-sm">
        {job.artist && job.title && (
          <p className="text-gray-700">
            <span className="font-medium">Track:</span> {job.artist} - {job.title}
          </p>
        )}
        {job.url && (
          <p className="text-gray-700">
            <span className="font-medium">Source:</span> {job.url}
          </p>
        )}
        {job.filename && (
          <p className="text-gray-700">
            <span className="font-medium">File:</span> {job.filename}
          </p>
        )}
        <p className="text-gray-600">
          <span className="font-medium">Created:</span>{' '}
          {new Date(job.created_at).toLocaleString()}
        </p>
      </div>

      {/* Error Message */}
      {job.status === JobStatusEnum.ERROR && job.error_message && (
        <div className="mt-4 bg-red-50 border border-red-200 rounded-md p-4">
          <h4 className="text-red-800 font-medium mb-2">Error Details</h4>
          <p className="text-red-600 text-sm">{job.error_message}</p>
        </div>
      )}

      {/* Download Links */}
      {job.status === JobStatusEnum.COMPLETE && job.download_urls && (
        <div className="mt-4">
          <h4 className="font-medium text-gray-800 mb-3">Download Results</h4>
          <div className="space-y-2">
            {Object.entries(job.download_urls).map(([key, url]) => (
              <a
                key={key}
                href={url}
                download
                className="block px-4 py-2 bg-green-50 border border-green-200 rounded-md text-green-700 hover:bg-green-100 transition-colors"
              >
                Download {key.replace(/_/g, ' ')}
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Timeline */}
      {job.timeline && job.timeline.length > 0 && (
        <details className="mt-4">
          <summary className="cursor-pointer text-sm font-medium text-gray-700">
            View Timeline ({job.timeline.length} events)
          </summary>
          <div className="mt-2 space-y-2 pl-4 border-l-2 border-gray-200">
            {job.timeline.map((event, index) => (
              <div key={index} className="text-sm">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-gray-700">{event.status}</span>
                  {event.progress !== undefined && (
                    <span className="text-gray-500">({event.progress}%)</span>
                  )}
                </div>
                {event.message && (
                  <p className="text-gray-600">{event.message}</p>
                )}
                <p className="text-gray-400 text-xs">
                  {new Date(event.timestamp).toLocaleString()}
                </p>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
};

