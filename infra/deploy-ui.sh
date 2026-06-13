#!/bin/bash
# Build and deploy the UI frontend to S3 + CloudFront.
# Requires: AWS CLI v2, Node.js 18+, and terraform outputs.
#
# Usage:
#   ./deploy-ui.sh                    # uses terraform output
#   ./deploy-ui.sh BUCKET_NAME DIST_ID  # explicit overrides

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
UI_DIR="$SCRIPT_DIR/../ui-frontend"
TFDIR="$SCRIPT_DIR/terraform"

if [ $# -ge 2 ]; then
    BUCKET="$1"
    DIST_ID="$2"
else
    cd "$TFDIR"
    BUCKET=$(terraform output -raw ui_assets_bucket 2>/dev/null || echo "")
    DIST_ID=$(terraform output -raw cloudfront_distribution_id 2>/dev/null || echo "")
    cd "$SCRIPT_DIR"
fi

if [ -z "${BUCKET:-}" ] || [ -z "${DIST_ID:-}" ]; then
    echo "ERROR: Could not determine S3 bucket or CloudFront distribution ID."
    echo "Run 'terraform apply' first, or pass them explicitly:"
    echo "  ./deploy-ui.sh BUCKET_NAME DISTRIBUTION_ID"
    exit 1
fi

echo "Building UI frontend..."
cd "$UI_DIR"
npm install --silent
npm run build -- --outDir dist

echo "Syncing to s3://$BUCKET..."
aws s3 sync dist/ "s3://$BUCKET" --delete --cache-control "max-age=3600"

echo "Invalidating CloudFront cache..."
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*" --no-cli-pager

echo "Deploy complete."
echo "CloudFront URL: $(aws cloudfront get-distribution --id "$DIST_ID" --query 'Distribution.DomainName' --output text)"
