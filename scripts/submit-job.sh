#!/bin/bash
# Submit a karaoke generation job and monitor its progress
# 
# Usage: ./scripts/submit-job.sh <filepath> <artist> <title>
#
# This script:
# 1. Uploads the audio file to the backend
# 2. Polls for job status with live updates
# 3. Opens the review UI when lyrics review is needed
# 4. Prompts for instrumental selection when needed
# 5. Shows download URLs when complete

set -e

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Configuration
SERVICE_URL="${SERVICE_URL:-https://karaoke-backend-718638054799.us-central1.run.app}"
REVIEW_UI_URL="${REVIEW_UI_URL:-http://localhost:5173}"
POLL_INTERVAL=${POLL_INTERVAL:-5}

# Print usage
usage() {
    echo "Usage: $0 <filepath> <artist> <title>"
    echo "       $0 --resume <job_id>"
    echo ""
    echo "Arguments:"
    echo "  filepath    Path to audio file (mp3, wav, flac, m4a, ogg, aac)"
    echo "  artist      Artist name"
    echo "  title       Song title"
    echo ""
    echo "Options:"
    echo "  --resume <job_id>   Resume monitoring an existing job"
    echo ""
    echo "Environment variables:"
    echo "  SERVICE_URL     Backend URL (default: production Cloud Run)"
    echo "  REVIEW_UI_URL   Lyrics review UI URL (default: http://localhost:5173)"
    echo "  POLL_INTERVAL   Seconds between status polls (default: 5)"
    echo ""
    echo "Examples:"
    echo "  $0 ./song.mp3 \"ABBA\" \"Waterloo\""
    echo "  $0 --resume abc12345"
    exit 1
}

# Check prerequisites
check_prerequisites() {
    if ! command -v curl &> /dev/null; then
        echo -e "${RED}Error: curl is required but not installed${NC}"
        exit 1
    fi
    
    if ! command -v jq &> /dev/null; then
        echo -e "${RED}Error: jq is required but not installed${NC}"
        echo "Install with: brew install jq"
        exit 1
    fi
    
    if ! command -v gcloud &> /dev/null; then
        echo -e "${RED}Error: gcloud CLI is required but not installed${NC}"
        exit 1
    fi
}

# Get authentication token
get_auth_token() {
    local token
    token=$(gcloud auth print-identity-token 2>/dev/null) || {
        echo -e "${RED}Error: Failed to get auth token. Run: gcloud auth login${NC}"
        exit 1
    }
    echo "$token"
}

# Print status with color
print_status() {
    local status="$1"
    local color=""
    
    case "$status" in
        pending|downloading)
            color="$YELLOW"
            ;;
        separating*|transcribing|correcting|generating*|applying*|rendering*|encoding|packaging)
            color="$BLUE"
            ;;
        awaiting_review|in_review|awaiting_instrumental_selection)
            color="$CYAN"
            ;;
        complete)
            color="$GREEN"
            ;;
        failed|error|cancelled)
            color="$RED"
            ;;
        *)
            color="$NC"
            ;;
    esac
    
    echo -e "${color}${status}${NC}"
}

# Print progress bar
print_progress_bar() {
    local progress=$1
    local width=40
    local filled=$((progress * width / 100))
    local empty=$((width - filled))
    
    printf "["
    printf "%${filled}s" | tr ' ' '█'
    printf "%${empty}s" | tr ' ' '░'
    printf "] %3d%%" "$progress"
}

# Submit job via file upload
submit_job() {
    local filepath="$1"
    local artist="$2"
    local title="$3"
    local auth_token="$4"
    
    echo -e "${BOLD}Uploading file...${NC}" >&2
    
    local response
    response=$(curl -s -X POST \
        -H "Authorization: Bearer $auth_token" \
        -F "file=@$filepath" \
        -F "artist=$artist" \
        -F "title=$title" \
        "$SERVICE_URL/api/jobs/upload")
    
    local status
    status=$(echo "$response" | jq -r '.status // "error"')
    
    if [ "$status" != "success" ]; then
        echo -e "${RED}Error submitting job:${NC}" >&2
        echo "$response" | jq . >&2
        exit 1
    fi
    
    local job_id
    job_id=$(echo "$response" | jq -r '.job_id')
    echo -e "${GREEN}✓ Job submitted: ${BOLD}$job_id${NC}" >&2
    echo "" >&2
    
    # Only the job_id goes to stdout for capture
    echo "$job_id"
}

# Get job status
get_job() {
    local job_id="$1"
    local auth_token="$2"
    
    curl -s -H "Authorization: Bearer $auth_token" \
        "$SERVICE_URL/api/jobs/$job_id"
}

# Open review UI in browser
open_review_ui() {
    local job_id="$1"
    local url="$REVIEW_UI_URL/?jobId=$job_id"
    
    echo -e "${CYAN}Opening lyrics review UI in browser...${NC}"
    echo -e "URL: ${BOLD}$url${NC}"
    echo ""
    
    # Open browser based on OS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        open "$url"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        xdg-open "$url" 2>/dev/null || echo "Please open: $url"
    else
        echo "Please open: $url"
    fi
}

# Handle lyrics review
handle_review() {
    local job_id="$1"
    local auth_token="$2"
    
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${CYAN}  LYRICS REVIEW NEEDED${NC}"
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "The transcription is ready for review."
    echo -e "Please review and correct the lyrics in the browser."
    echo ""
    
    open_review_ui "$job_id"
    
    echo -e "${YELLOW}Press Enter when you have completed the review...${NC}"
    read -r
    
    # After review, trigger complete-review endpoint
    echo -e "Completing review..."
    local response
    response=$(curl -s -X POST \
        -H "Authorization: Bearer $auth_token" \
        -H "Content-Type: application/json" \
        "$SERVICE_URL/api/jobs/$job_id/complete-review")
    
    local status
    status=$(echo "$response" | jq -r '.status // "error"')
    
    if [ "$status" == "success" ]; then
        echo -e "${GREEN}✓ Review completed${NC}"
    else
        echo -e "${RED}Warning: Could not complete review:${NC}"
        echo "$response" | jq .
        echo ""
        echo "The job may have already been completed or there was an error."
    fi
    echo ""
}

# Handle instrumental selection
handle_instrumental_selection() {
    local job_id="$1"
    local auth_token="$2"
    
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${CYAN}  INSTRUMENTAL SELECTION NEEDED${NC}"
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    # Get instrumental options
    local options_response
    options_response=$(curl -s -H "Authorization: Bearer $auth_token" \
        "$SERVICE_URL/api/jobs/$job_id/instrumental-options")
    
    local options_status
    options_status=$(echo "$options_response" | jq -r '.status // "awaiting_instrumental_selection"')
    
    echo -e "Choose which instrumental track to use for the final video:"
    echo ""
    echo -e "  ${BOLD}1)${NC} Clean Instrumental (no backing vocals)"
    echo -e "     Best for songs where you want ONLY the lead vocal removed"
    echo ""
    echo -e "  ${BOLD}2)${NC} Instrumental with Backing Vocals"
    echo -e "     Best for songs where backing vocals add to the karaoke experience"
    echo ""
    
    # Extract audio URLs for playback hint
    local clean_url
    local backing_url
    clean_url=$(echo "$options_response" | jq -r '.options[0].audio_url // empty')
    backing_url=$(echo "$options_response" | jq -r '.options[1].audio_url // empty')
    
    if [ -n "$clean_url" ]; then
        echo -e "${CYAN}Tip: You can preview the audio files:${NC}"
        echo -e "  Clean:   $clean_url"
        echo -e "  Backing: $backing_url"
        echo ""
    fi
    
    local selection=""
    while [ -z "$selection" ]; do
        read -rp "Enter your choice (1 or 2): " choice
        case "$choice" in
            1)
                selection="clean"
                ;;
            2)
                selection="with_backing"
                ;;
            *)
                echo -e "${RED}Invalid choice. Please enter 1 or 2.${NC}"
                ;;
        esac
    done
    
    echo ""
    echo -e "Submitting selection: ${BOLD}$selection${NC}..."
    
    local response
    response=$(curl -s -X POST \
        -H "Authorization: Bearer $auth_token" \
        -H "Content-Type: application/json" \
        -d "{\"selection\": \"$selection\"}" \
        "$SERVICE_URL/api/jobs/$job_id/select-instrumental")
    
    local status
    status=$(echo "$response" | jq -r '.status // "error"')
    
    if [ "$status" == "success" ]; then
        echo -e "${GREEN}✓ Selection submitted: $selection${NC}"
    else
        echo -e "${RED}Error submitting selection:${NC}"
        echo "$response" | jq .
    fi
    echo ""
}

# Display job completion info
show_completion_info() {
    local job_response="$1"
    
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${GREEN}  JOB COMPLETE!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    # Show output files
    local output_files
    output_files=$(echo "$job_response" | jq -r '.output_files // {}')
    
    if [ "$output_files" != "{}" ] && [ "$output_files" != "null" ]; then
        echo -e "${BOLD}Output Files:${NC}"
        echo "$output_files" | jq -r 'to_entries[] | "  \(.key): \(.value)"'
        echo ""
    fi
    
    # Show download URLs
    local download_urls
    download_urls=$(echo "$job_response" | jq -r '.download_urls // {}')
    
    if [ "$download_urls" != "{}" ] && [ "$download_urls" != "null" ]; then
        echo -e "${BOLD}Download URLs:${NC}"
        echo "$download_urls" | jq -r 'to_entries[] | "  \(.key): \(.value)"' 2>/dev/null || \
            echo "$download_urls" | jq .
        echo ""
    fi
}

# Display error info
show_error_info() {
    local job_response="$1"
    
    echo -e "${RED}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${RED}  JOB FAILED${NC}"
    echo -e "${RED}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    local error_message
    error_message=$(echo "$job_response" | jq -r '.error_message // "Unknown error"')
    echo -e "${RED}Error: $error_message${NC}"
    
    local error_details
    error_details=$(echo "$job_response" | jq -r '.error_details // empty')
    if [ -n "$error_details" ] && [ "$error_details" != "null" ]; then
        echo ""
        echo -e "${BOLD}Details:${NC}"
        echo "$error_details"
    fi
    echo ""
}

# Main monitoring loop
monitor_job() {
    local job_id="$1"
    local auth_token="$2"
    
    local last_status=""
    local last_message=""
    local review_opened=false
    local instrumental_prompted=false
    
    echo -e "${BOLD}Monitoring job: $job_id${NC}"
    echo -e "Service: $SERVICE_URL"
    echo ""
    
    while true; do
        local job_response
        job_response=$(get_job "$job_id" "$auth_token")
        
        local status
        local progress
        local message
        local artist
        local title
        
        status=$(echo "$job_response" | jq -r '.status // "unknown"')
        progress=$(echo "$job_response" | jq -r '.progress // 0')
        message=$(echo "$job_response" | jq -r '.timeline[-1].message // ""')
        artist=$(echo "$job_response" | jq -r '.artist // ""')
        title=$(echo "$job_response" | jq -r '.title // ""')
        
        # Only update display if something changed
        if [ "$status" != "$last_status" ] || [ "$message" != "$last_message" ]; then
            # Clear line and print status
            printf "\r\033[K"
            echo -e "$(print_status "$status") | $(print_progress_bar "$progress") | $message"
            
            last_status="$status"
            last_message="$message"
        fi
        
        # Handle human interaction points
        case "$status" in
            awaiting_review|in_review)
                if [ "$review_opened" = false ]; then
                    echo ""
                    handle_review "$job_id" "$auth_token"
                    review_opened=true
                    # Refresh auth token after potentially long review
                    auth_token=$(get_auth_token)
                fi
                ;;
            awaiting_instrumental_selection)
                if [ "$instrumental_prompted" = false ]; then
                    echo ""
                    handle_instrumental_selection "$job_id" "$auth_token"
                    instrumental_prompted=true
                fi
                ;;
            complete)
                echo ""
                show_completion_info "$job_response"
                return 0
                ;;
            failed|error)
                echo ""
                show_error_info "$job_response"
                return 1
                ;;
            cancelled)
                echo ""
                echo -e "${YELLOW}Job was cancelled${NC}"
                return 1
                ;;
        esac
        
        sleep "$POLL_INTERVAL"
    done
}

# Resume an existing job
resume_job() {
    local job_id="$1"
    
    check_prerequisites
    
    echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}  Karaoke Generator - Resume Job${NC}"
    echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  Job ID: ${CYAN}$job_id${NC}"
    echo ""
    
    # Get auth token
    echo -e "Authenticating..."
    local auth_token
    auth_token=$(get_auth_token)
    echo -e "${GREEN}✓ Authenticated${NC}"
    echo ""
    
    # Verify job exists
    local job_response
    job_response=$(get_job "$job_id" "$auth_token")
    
    local status
    status=$(echo "$job_response" | jq -r '.status // "not_found"')
    
    if [ "$status" == "not_found" ] || [ "$status" == "null" ]; then
        echo -e "${RED}Error: Job not found: $job_id${NC}"
        exit 1
    fi
    
    local artist
    local title
    artist=$(echo "$job_response" | jq -r '.artist // "Unknown"')
    title=$(echo "$job_response" | jq -r '.title // "Unknown"')
    
    echo -e "  Artist: ${CYAN}$artist${NC}"
    echo -e "  Title:  ${CYAN}$title${NC}"
    echo -e "  Status: $(print_status "$status")"
    echo ""
    
    # Monitor job
    monitor_job "$job_id" "$auth_token"
}

# Main
main() {
    # Check for resume mode
    if [ "$1" == "--resume" ] || [ "$1" == "-r" ]; then
        if [ -z "$2" ]; then
            echo -e "${RED}Error: --resume requires a job ID${NC}"
            usage
        fi
        resume_job "$2"
        exit $?
    fi
    
    # Check arguments for normal submission
    if [ $# -lt 3 ]; then
        usage
    fi
    
    local filepath="$1"
    local artist="$2"
    local title="$3"
    
    # Validate file exists
    if [ ! -f "$filepath" ]; then
        echo -e "${RED}Error: File not found: $filepath${NC}"
        exit 1
    fi
    
    # Check file extension
    local ext="${filepath##*.}"
    ext=$(echo "$ext" | tr '[:upper:]' '[:lower:]')
    case "$ext" in
        mp3|wav|flac|m4a|ogg|aac)
            ;;
        *)
            echo -e "${RED}Error: Unsupported file type: .$ext${NC}"
            echo "Supported: mp3, wav, flac, m4a, ogg, aac"
            exit 1
            ;;
    esac
    
    check_prerequisites
    
    echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}  Karaoke Generator - Job Submission${NC}"
    echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  File:   ${CYAN}$filepath${NC}"
    echo -e "  Artist: ${CYAN}$artist${NC}"
    echo -e "  Title:  ${CYAN}$title${NC}"
    echo ""
    
    # Get auth token
    echo -e "Authenticating..."
    local auth_token
    auth_token=$(get_auth_token)
    echo -e "${GREEN}✓ Authenticated${NC}"
    echo ""
    
    # Submit job
    local job_id
    job_id=$(submit_job "$filepath" "$artist" "$title" "$auth_token")
    
    # Monitor job
    monitor_job "$job_id" "$auth_token"
}

main "$@"
