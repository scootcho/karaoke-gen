/**
 * Main App component
 */
import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { JobSubmission } from './components/JobSubmission';
import { JobStatus } from './components/JobStatus';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 py-12 px-4">
        <div className="max-w-4xl mx-auto">
          <header className="text-center mb-12">
            <h1 className="text-4xl font-bold text-gray-900 mb-2">
              Karaoke Generator
            </h1>
            <p className="text-gray-600">
              Generate professional karaoke videos with synchronized lyrics
            </p>
          </header>

          <main className="space-y-6">
            <JobSubmission />
            <JobStatus />
          </main>

          <footer className="text-center mt-12 text-gray-500 text-sm">
            <p>Powered by Nomad Karaoke</p>
          </footer>
        </div>
      </div>
    </QueryClientProvider>
  );
}

export default App;
