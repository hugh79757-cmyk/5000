#!/bin/bash

################################################################################
# ETAP Bulk Deployment Script v2.2
# Deploy all 26 Hugo sites to Cloudflare Pages
# Usage: ./bulk_deploy_all.sh [--quick | --full | --fix]
################################################################################

set -e

# ========== CONFIG ==========
PROJECT_ROOT="/Users/twinssn/Projects/5000"
ETAP_ROOT="/Users/twinssn/Projects/ETAP"
HUGO_BIN="/opt/homebrew/bin/hugo"
WRANGLER_BIN="/opt/homebrew/bin/wrangler"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

MODE="${1:---full}"

TOTAL=0
SUCCEEDED=0
FAILED=0
FAILED_SITES=""
START_TIME=$(date +%s)

declare -a BLOGS=(
  "tour-hugo"
  "flights-hugo"
  "airlines-hugo"
  "airports-hugo"
  "esim-hugo"
  "michelin-hugo"
  "tours-hugo"
  "trains-hugo"
  "visa-hugo"
  "daytrips-hugo"
  "walking-hugo"
  "foodtour-hugo"
  "adventure-hugo"
  "watersports-hugo"
  "bus-hugo"
  "ferry-hugo"
  "dining-hugo"
  "culture-hugo"
  "transfers-hugo"
  "multiday-hugo"
  "nature-hugo"
  "visafree-hugo"
  "deals-hugo"
  "eurail-hugo"
  "cruise-hugo"
  "phototour-hugo"
)

# ========== FUNCTIONS ==========

log_info() {
  echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
  echo -e "${GREEN}[✓]${NC} $1"
}

log_error() {
  echo -e "${RED}[✗]${NC} $1"
}

log_warn() {
  echo -e "${YELLOW}[!]${NC} $1"
}

print_header() {
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "$1"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

print_footer() {
  END_TIME=$(date +%s)
  ELAPSED=$((END_TIME - START_TIME))
  MIN=$((ELAPSED / 60))
  SEC=$((ELAPSED % 60))
  
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "DEPLOYMENT SUMMARY"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "Total: ${TOTAL}"
  echo -e "Succeeded: ${GREEN}${SUCCEEDED}${NC}"
  echo -e "Failed: ${RED}${FAILED}${NC}"
  echo "Time: ${MIN}m ${SEC}s"
  
  if [ $FAILED -gt 0 ]; then
    echo -e "\n${RED}Failed sites:${NC}"
    echo -e "$FAILED_SITES"
  fi
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

validate_tools() {
  log_info "Validating tools..."
  
  if ! command -v "$HUGO_BIN" &> /dev/null; then
    log_error "Hugo not found at $HUGO_BIN"
    exit 1
  fi
  
  if ! command -v "$WRANGLER_BIN" &> /dev/null; then
    log_error "Wrangler not found at $WRANGLER_BIN"
    exit 1
  fi
  
  log_success "Hugo v$($HUGO_BIN version | cut -d' ' -f2)"
  log_success "Wrangler v$($WRANGLER_BIN --version | cut -d' ' -f2)"
}

validate_blog_dir() {
  local blog=$1
  local blog_dir="$ETAP_ROOT/$blog"
  
  if [ ! -d "$blog_dir" ]; then
    return 1
  fi
  
  # Hugo 설정 파일 확인 (hugo.yaml 확인)
  if [ ! -f "$blog_dir/hugo.yaml" ]; then
    return 1
  fi
  
  return 0
}

build_blog() {
  local blog=$1
  local blog_dir="$ETAP_ROOT/$blog"
  
  log_info "Building $blog..."
  
  if ! validate_blog_dir "$blog"; then
    log_error "Hugo site not found: $blog_dir (no hugo.yaml)"
    return 1
  fi
  
  cd "$blog_dir"
  
  # Remove old public dir
  rm -rf public/
  
  # Build with minification and garbage collection
  if ! "$HUGO_BIN" --gc --minify 2>&1 | tail -3; then
    log_error "Hugo build failed for $blog"
    cd - > /dev/null
    return 1
  fi
  
  if [ ! -d "public/" ]; then
    log_error "Hugo output not found: $blog_dir/public/"
    cd - > /dev/null
    return 1
  fi
  
  # Check file count
  FILE_COUNT=$(find public -type f | wc -l)
  if [ $FILE_COUNT -gt 19500 ]; then
    log_warn "$blog: $FILE_COUNT files (approaching 20,000 Cloudflare limit)"
  fi
  
  log_success "$blog built: $FILE_COUNT files"
  cd - > /dev/null
  return 0
}

deploy_blog() {
  local blog=$1
  local blog_dir="$ETAP_ROOT/$blog"
  
  log_info "Deploying $blog to Cloudflare Pages..."
  
  cd "$blog_dir"
  
  if [ ! -d "public/" ]; then
    log_error "No public/ dir found for $blog"
    cd - > /dev/null
    return 1
  fi
  
  # Deploy with wrangler
  if ! "$WRANGLER_BIN" pages deploy public/ --project-name="$blog" 2>&1 | tail -3; then
    log_error "Wrangler deploy failed for $blog"
    cd - > /dev/null
    return 1
  fi
  
  log_success "$blog deployed"
  cd - > /dev/null
  return 0
}

# ========== MAIN ==========

print_header "ETAP BULK DEPLOYMENT v2.2"
echo "Mode: $MODE"
echo "Start time: $(date)"
echo "Blogs to deploy: ${#BLOGS[@]}"

validate_tools

case "$MODE" in
  --quick)
    print_header "QUICK DEPLOYMENT (deploy only, skip builds)"
    for blog in "${BLOGS[@]}"; do
      TOTAL=$((TOTAL + 1))
      if deploy_blog "$blog"; then
        SUCCEEDED=$((SUCCEEDED + 1))
      else
        FAILED=$((FAILED + 1))
        FAILED_SITES="$FAILED_SITES\n  - $blog"
      fi
      sleep 2
    done
    ;;
    
  --full)
    print_header "FULL DEPLOYMENT (build + deploy all 26)"
    for blog in "${BLOGS[@]}"; do
      TOTAL=$((TOTAL + 1))
      
      if build_blog "$blog" && deploy_blog "$blog"; then
        SUCCEEDED=$((SUCCEEDED + 1))
      else
        FAILED=$((FAILED + 1))
        FAILED_SITES="$FAILED_SITES\n  - $blog"
      fi
      
      sleep 2
    done
    ;;
    
  --fix)
    print_header "FIX DEPLOYMENT (Batch 3)"
    BATCH3=("nature-hugo" "visafree-hugo" "deals-hugo" "eurail-hugo" "cruise-hugo" "phototour-hugo")
    
    for blog in "${BATCH3[@]}"; do
      TOTAL=$((TOTAL + 1))
      
      if build_blog "$blog" && deploy_blog "$blog"; then
        SUCCEEDED=$((SUCCEEDED + 1))
      else
        FAILED=$((FAILED + 1))
        FAILED_SITES="$FAILED_SITES\n  - $blog"
      fi
      sleep 2
    done
    ;;
    
  *)
    log_error "Unknown mode: $MODE"
    echo "Usage: $0 [--quick | --full | --fix]"
    exit 1
    ;;
esac

print_footer

if [ $FAILED -eq 0 ]; then
  exit 0
else
  exit 1
fi
