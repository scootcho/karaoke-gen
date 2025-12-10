import type { JobStatus } from "@/lib/types"
import { Badge } from "@/components/ui/badge"

interface StatusBadgeProps {
  status: JobStatus
  size?: "sm" | "md" | "lg"
}

export function StatusBadge({ status, size = "md" }: StatusBadgeProps) {
  const getStatusColor = () => {
    switch (status) {
      case "queued":
        return "bg-muted text-muted-foreground"
      case "processing":
        return "bg-blue-500/20 text-blue-400 border-blue-500/30"
      case "awaiting_review":
      case "awaiting_instrumental":
        return "bg-secondary/20 text-secondary border-secondary/30"
      case "completed":
        return "bg-green-500/20 text-green-400 border-green-500/30"
      case "failed":
        return "bg-destructive/20 text-destructive border-destructive/30"
      default:
        return "bg-muted text-muted-foreground"
    }
  }

  const getStatusLabel = () => {
    switch (status) {
      case "queued":
        return "Queued"
      case "processing":
        return "Processing"
      case "awaiting_review":
        return "Awaiting Review"
      case "awaiting_instrumental":
        return "Select Instrumental"
      case "completed":
        return "Completed"
      case "failed":
        return "Failed"
      default:
        return status
    }
  }

  const sizeClass =
    size === "lg" ? "text-sm px-3 py-1" : size === "sm" ? "text-xs px-2 py-0.5" : "text-sm px-2.5 py-0.5"

  return (
    <Badge variant="outline" className={`${getStatusColor()} ${sizeClass} border`}>
      {getStatusLabel()}
    </Badge>
  )
}
