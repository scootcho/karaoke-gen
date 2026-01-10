import { JobRouterClient } from "./client"

// Required for static export with catch-all routes
// Returns params array for paths to pre-render at build time
// Empty slug array creates the base /app/jobs/ route
export async function generateStaticParams(): Promise<{ slug?: string[] }[]> {
  return [
    { slug: undefined }, // /app/jobs/
  ]
}

export default function JobsPage() {
  return <JobRouterClient />
}
