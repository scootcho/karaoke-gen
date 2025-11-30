/**
 * Job submission component with URL input and file upload
 */
import React, { useState } from 'react';
import { useSubmitJobFromUrl, useSubmitJobFromUpload } from '../hooks/useJobSubmit';
import { useAppStore } from '../stores/appStore';

export const JobSubmission: React.FC = () => {
  const [url, setUrl] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [artist, setArtist] = useState('');
  const [title, setTitle] = useState('');
  const [mode, setMode] = useState<'url' | 'upload'>('url');

  const { isUploadMode, setUploadMode } = useAppStore();
  const setCurrentJobId = useAppStore((state) => state.setCurrentJobId);

  const submitFromUrl = useSubmitJobFromUrl();
  const submitFromUpload = useSubmitJobFromUpload();

  const handleSubmitUrl = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const response = await submitFromUrl.mutateAsync({ url });
      setCurrentJobId(response.job_id);
      setUrl('');
    } catch (error) {
      console.error('Error submitting job:', error);
    }
  };

  const handleSubmitUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    
    try {
      const response = await submitFromUpload.mutateAsync({ file, artist, title });
      setCurrentJobId(response.job_id);
      setFile(null);
      setArtist('');
      setTitle('');
    } catch (error) {
      console.error('Error uploading file:', error);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto p-6 bg-white rounded-lg shadow-lg">
      <h2 className="text-2xl font-bold mb-6 text-gray-800">Create Karaoke Video</h2>
      
      {/* Mode Toggle */}
      <div className="flex gap-4 mb-6">
        <button
          onClick={() => setMode('url')}
          className={`flex-1 py-2 px-4 rounded-md font-medium transition-colors ${
            mode === 'url'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          From URL
        </button>
        <button
          onClick={() => setMode('upload')}
          className={`flex-1 py-2 px-4 rounded-md font-medium transition-colors ${
            mode === 'upload'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          Upload File
        </button>
      </div>

      {/* URL Mode */}
      {mode === 'url' && (
        <form onSubmit={handleSubmitUrl} className="space-y-4">
          <div>
            <label htmlFor="url" className="block text-sm font-medium text-gray-700 mb-2">
              YouTube URL or Audio Link
            </label>
            <input
              type="url"
              id="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://www.youtube.com/watch?v=..."
              required
              className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <button
            type="submit"
            disabled={submitFromUrl.isPending || !url}
            className="w-full py-3 px-4 bg-blue-600 text-white font-medium rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
          >
            {submitFromUrl.isPending ? 'Submitting...' : 'Generate Karaoke'}
          </button>
          {submitFromUrl.isError && (
            <p className="text-red-600 text-sm mt-2">
              Error: {submitFromUrl.error.message}
            </p>
          )}
        </form>
      )}

      {/* Upload Mode */}
      {mode === 'upload' && (
        <form onSubmit={handleSubmitUpload} className="space-y-4">
          <div>
            <label htmlFor="file" className="block text-sm font-medium text-gray-700 mb-2">
              Audio File
            </label>
            <input
              type="file"
              id="file"
              onChange={handleFileChange}
              accept=".mp3,.wav,.flac,.m4a,.ogg"
              required
              className="w-full px-4 py-2 border border-gray-300 rounded-md file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
            />
            {file && (
              <p className="text-sm text-gray-600 mt-2">
                Selected: {file.name} ({(file.size / 1024 / 1024).toFixed(2)} MB)
              </p>
            )}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="artist" className="block text-sm font-medium text-gray-700 mb-2">
                Artist
              </label>
              <input
                type="text"
                id="artist"
                value={artist}
                onChange={(e) => setArtist(e.target.value)}
                placeholder="Artist name"
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <div>
              <label htmlFor="title" className="block text-sm font-medium text-gray-700 mb-2">
                Song Title
              </label>
              <input
                type="text"
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Song title"
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>
          <button
            type="submit"
            disabled={submitFromUpload.isPending || !file || !artist || !title}
            className="w-full py-3 px-4 bg-blue-600 text-white font-medium rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
          >
            {submitFromUpload.isPending ? 'Uploading...' : 'Upload and Generate'}
          </button>
          {submitFromUpload.isError && (
            <p className="text-red-600 text-sm mt-2">
              Error: {submitFromUpload.error.message}
            </p>
          )}
        </form>
      )}
    </div>
  );
};

