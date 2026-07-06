#!/bin/bash
# Daily pre-computation runner script
# Run via cron at 2:00 AM: 0 2 * * * /path/to/run_precompute.sh
#
# Or add to crontab manually:
#   crontab -e
#   0 2 * * * /home/aaron/Projects/personal/de-trains-speed-map/backend/scripts/run_precompute.sh

set -e

# Configuration
PROJECT_DIR="/home/aaron/Projects/personal/de-trains-speed-map"
CONDA_ENV="trainmap"
LOG_DIR="${PROJECT_DIR}/logs"
DATE=$(date +%Y-%m-%d)
LOG_FILE="${LOG_DIR}/precompute_${DATE}.log"

# Create log directory if it doesn't exist
mkdir -p "${LOG_DIR}"

# Log start time
echo "========================================" >> "${LOG_FILE}"
echo "Pre-computation started at $(date)" >> "${LOG_FILE}"
echo "========================================" >> "${LOG_FILE}"

# Change to project directory
cd "${PROJECT_DIR}"

# Activate conda environment and run the script
# Using 'source' for conda activation in bash
eval "$(conda shell.bash hook)"
mamba activate "${CONDA_ENV}"

# Run pre-computation script
python backend/scripts/precompute_connections.py 2>&1 | tee -a "${LOG_FILE}"

EXIT_CODE=${PIPESTATUS[0]}

# Log completion
echo "========================================" >> "${LOG_FILE}"
if [ $EXIT_CODE -eq 0 ]; then
    echo "Pre-computation completed successfully at $(date)" >> "${LOG_FILE}"
else
    echo "Pre-computation FAILED with exit code ${EXIT_CODE} at $(date)" >> "${LOG_FILE}"
    # Optional: send notification on failure
    # curl -X POST "https://your-webhook.com" -d "Pre-computation failed"
fi
echo "========================================" >> "${LOG_FILE}"

exit $EXIT_CODE
