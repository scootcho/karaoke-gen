# Frontend React Application

Modern React + TypeScript frontend for the karaoke generation web application.

## Tech Stack

- **React 18** with TypeScript
- **Vite** for fast development and optimized builds
- **TanStack Query** for server state management
- **Axios** for API calls
- **Zustand** for client state
- **Tailwind CSS** for styling

## Development

### Prerequisites

- Node.js 18+ and npm

### Setup

```bash
cd frontend-react
npm install
```

### Running Locally

```bash
# Start development server
npm run dev

# Access at http://localhost:5173
```

### Environment Variables

Create a `.env.local` file:

```
VITE_API_URL=http://localhost:8080/api
```

For production, set `VITE_API_URL` to your Cloud Run backend URL.

## Building for Production

```bash
npm run build
```

Output will be in the `dist/` directory, ready for deployment to Cloudflare Pages.

## Project Structure

```
src/
├── components/        # React components
│   ├── JobSubmission.tsx
│   └── JobStatus.tsx
├── hooks/            # Custom React hooks
│   ├── useJobSubmit.ts
│   └── useJobStatus.ts
├── services/         # API service layer
│   └── api.ts
├── stores/           # Zustand state stores
│   └── appStore.ts
├── types/            # TypeScript types
│   └── job.ts
├── App.tsx           # Main app component
├── main.tsx          # Entry point
└── index.css         # Global styles
```

## Features

### Job Submission

- Submit jobs from YouTube URLs
- Upload audio files directly
- Artist and title input for uploads

### Status Tracking

- Real-time job status updates with polling
- Progress bar for active jobs
- Timeline view of job events
- Download links for completed jobs

### Error Handling

- User-friendly error messages
- API error handling
- Loading states

## Deployment to Cloudflare Pages

### Via Cloudflare Dashboard

1. Connect your GitHub repository
2. Set build command: `npm run build`
3. Set build output directory: `dist`
4. Add environment variable: `VITE_API_URL=https://your-cloud-run-url/api`
5. Deploy!

### Via Wrangler CLI

```bash
npx wrangler pages deploy dist --project-name=karaoke-gen
```

## API Integration

The frontend communicates with the FastAPI backend running on Google Cloud Run. See `src/services/api.ts` for API endpoints.

## Type Safety

TypeScript is used throughout for type safety. Types are defined in `src/types/` and match the backend API models.

Run type checking:

```bash
npm run type-check
```
