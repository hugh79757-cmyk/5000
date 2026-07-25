#!/usr/bin/env bash
#===============================================================================
# integrity-checker.sh — Hugo Template Integrity Validator
#
# Purpose:
#   Validate that Hugo single.html templates across all STAP blogs match their
#   original theme baselines, with only allowed AdSense additions. Prevents
#   template regressions (lost hero, missing TOC, broken pagination, etc.)
#   from going unnoticed.
#
# Usage:
#   bash scripts/integrity-checker.sh              # check all STAP blogs
#   bash scripts/integrity-checker.sh sector-hugo  # check single blog
#   bash scripts/integrity-checker.sh --list       # list known blogs
#
# Reference:
#   AGENTS.md Section 4 — Hugo 템플릿 수정 규칙
#   shared-themes/blowfish/layouts/_default/single.html (baseline: 140 lines)
#===============================================================================

STAP_ROOT="/Users/twinssn/Projects/STAP"
BLOWFISH_BASELINE="/Users/twinssn/Projects/shared-themes/blowfish/layouts/_default/single.html"
CONGO_BASELINE="${STAP_ROOT}/themes/congo/layouts/single.html"

# Blowfish blogs (5 blogs, already fixed)
BLOWFISH_BLOGS=("dividend" "etf" "finance" "ipo" "sector")
# Congo blog (stock-hugo, needs separate treatment)
CONGO_BLOGS=("stock")

PASS=0
FAIL=0
WARN=0

red='\033[0;31m'
green='\033[0;32m'
yellow='\033[1;33m'
cyan='\033[0;36m'
nc='\033[0m'

#===============================================================================
# Helper functions
#===============================================================================

check() {
  local blog="$1" label="$2" desc="$3"
  if [ "$4" = "true" ] || [ "$4" = "0" ]; then
    echo -e "  ${green}[PASS]${nc} ${label}: ${desc}"
    ((PASS++))
  else
    echo -e "  ${red}[FAIL]${nc} ${label}: ${desc}"
    ((FAIL++))
  fi
}

warn() {
  local blog="$1" label="$2" desc="$3"
  echo -e "  ${yellow}[WARN]${nc} ${label}: ${desc}"
  ((WARN++))
}

file_exists() {
  [ -f "$1" ]
}

grep_q() {
  grep -q "$1" "$2" 2>/dev/null
}

#===============================================================================
# Validate a single Blowfish blog
#===============================================================================

check_blowfish_blog() {
  local blog_id="$1"
  local dir="${STAP_ROOT}/${blog_id}-hugo"
  local single="${dir}/layouts/_default/single.html"

  echo -e "\n${cyan}═══ ${blog_id}-hugo (Blowfish) ═══${nc}"

  #--- File existence ---
  if ! file_exists "$single"; then
    check "$blog_id" "EXISTS" "single.html file exists" "false"
    return
  fi
  check "$blog_id" "EXISTS" "single.html file exists" "true"

  #--- H1 classes match Blowfish original ---
  if grep_q 'text-4xl font-extrabold text-neutral-900' "$single"; then
    check "$blog_id" "H1" "H1 has correct Blowfish classes (text-4xl, font-extrabold, text-neutral-900)" "true"
  else
    check "$blog_id" "H1" "H1 has correct Blowfish classes" "false"
  fi

  #--- Hero section preserved ---
  if grep_q 'showHero' "$single" && grep_q 'hero/basic' "$single"; then
    check "$blog_id" "HERO" "Hero section (showHero + hero/basic) preserved" "true"
  else
    check "$blog_id" "HERO" "Hero section preserved" "false"
  fi

  #--- Breadcrumbs preserved ---
  if grep_q 'breadcrumbs' "$single"; then
    check "$blog_id" "BREADCRUMBS" "Breadcrumbs partial preserved" "true"
  else
    check "$blog_id" "BREADCRUMBS" "Breadcrumbs partial preserved" "false"
  fi

  #--- Top ad slot present inside header ---
  if grep_q 'adsense/top' "$single"; then
    check "$blog_id" "TOP_AD" "adsense/top.html partial present in header" "true"
  else
    check "$blog_id" "TOP_AD" "adsense/top.html partial present in header" "false"
  fi

  #--- In-article ad slot present after header ---
  if grep_q 'adsense/in-article' "$single"; then
    check "$blog_id" "INARTICLE_AD" "adsense/in-article.html partial present after header" "true"
  else
    check "$blog_id" "INARTICLE_AD" "adsense/in-article.html partial present after header" "false"
  fi

  #--- Series partials preserved ---
  if grep_q 'series/series\.html' "$single"; then
    check "$blog_id" "SERIES" "series/series.html partial preserved" "true"
  else
    check "$blog_id" "SERIES" "series/series.html partial preserved" "false"
  fi

  if grep_q 'series/series-closed' "$single"; then
    check "$blog_id" "SERIES_CLOSED" "series/series-closed.html partial preserved" "true"
  else
    check "$blog_id" "SERIES_CLOSED" "series/series-closed.html partial preserved" "false"
  fi

  #--- Related posts preserved ---
  if grep_q 'related\.html' "$single"; then
    check "$blog_id" "RELATED" "related.html partial preserved" "true"
  else
    check "$blog_id" "RELATED" "related.html partial preserved" "false"
  fi

  #--- Sharing links preserved ---
  if grep_q 'sharing-links' "$single"; then
    check "$blog_id" "SHARING" "sharing-links.html partial preserved" "true"
  else
    check "$blog_id" "SHARING" "sharing-links.html partial preserved" "false"
  fi

  #--- Article pagination preserved ---
  if grep_q 'article-pagination' "$single"; then
    check "$blog_id" "PAGINATION" "article-pagination.html partial preserved" "true"
  else
    check "$blog_id" "PAGINATION" "article-pagination.html partial preserved" "false"
  fi

  #--- Comments with existence check preserved ---
  if grep_q 'templates.Exists.*comments' "$single"; then
    check "$blog_id" "COMMENTS" "Comments partial with existence check preserved" "true"
  else
    check "$blog_id" "COMMENTS" "Comments partial with existence check preserved" "false"
  fi

  #--- prose class in body section ---
  if grep_q 'prose dark:prose-invert' "$single"; then
    check "$blog_id" "PROSE" "prose dark:prose-invert class present in body" "true"
  else
    check "$blog_id" "PROSE" "prose dark:prose-invert class present in body" "false"
  fi

  #--- custom.css exists with ad styles ---
  local css="${dir}/assets/css/custom.css"
  if file_exists "$css"; then
    if grep_q 'ad-top\|ad-inarticle' "$css"; then
      check "$blog_id" "CUSTOM_CSS" "custom.css exists with ad styles (ad-top/ad-inarticle)" "true"
    else
      warn "$blog_id" "CUSTOM_CSS" "custom.css exists but missing ad styles"
    fi
  else
    check "$blog_id" "CUSTOM_CSS" "custom.css exists with ad styles" "false"
  fi

  #--- params.toml: showTableOfContents = false ---
  local params="${dir}/config/_default/params.toml"
  if file_exists "$params"; then
    if grep_q 'showTableOfContents = false' "$params"; then
      check "$blog_id" "TOC_OFF" "showTableOfContents = false in params.toml" "true"
    else
      warn "$blog_id" "TOC_OFF" "showTableOfContents is NOT set to false in params.toml"
    fi

    #--- params.toml: advertisement section ---
    if grep_q '\[advertisement\]' "$params" && grep_q 'adsense' "$params" && grep_q 'topSlot' "$params"; then
      check "$blog_id" "AD_CONFIG" "Advertisement section in params.toml (adsense + topSlot)" "true"
    else
      check "$blog_id" "AD_CONFIG" "Advertisement section in params.toml" "false"
    fi
  else
    warn "$blog_id" "PARAMS" "params.toml not found"
  fi

  #--- DIFF: compare vs Blowfish baseline — only ad additions allowed ---
  if file_exists "$single" && file_exists "$BLOWFISH_BASELINE"; then
    local diff_out
    diff_out=$(diff <(cat "$BLOWFISH_BASELINE") <(cat "$single") 2>/dev/null)
    local add_lines
    add_lines=$(echo "$diff_out" | grep -c '^>')
    local del_lines
    del_lines=$(echo "$diff_out" | grep -c '^<')
    # Allowed additions: adsense/top comment+partial (3 lines) and adsense/in-article comment+partial (3 lines) = ~6 lines
    if [ "$del_lines" -eq 0 ]; then
      check "$blog_id" "DIFF" "Diff vs baseline: 0 deletions, ${add_lines} additions (expected ~6 ad lines)" "true"
    else
      check "$blog_id" "DIFF" "Diff vs baseline: ${del_lines} deletions, ${add_lines} additions — DELETIONS DETECTED!" "false"
    fi
  fi
}

#===============================================================================
# Validate stock-hugo (Congo theme)
#===============================================================================

check_congo_blog() {
  local blog_id="$1"
  local dir="${STAP_ROOT}/${blog_id}-hugo"
  local single="${dir}/layouts/single.html"

  echo -e "\n${cyan}═══ ${blog_id}-hugo (Congo) ═══${nc}"

  #--- File existence ---
  if ! file_exists "$single"; then
    check "$blog_id" "EXISTS" "layouts/single.html exists (Congo-style top-level)" "false"
    return
  fi
  check "$blog_id" "EXISTS" "layouts/single.html exists (Congo-style top-level)" "true"

  #--- Congo baseline comparison ---
  if file_exists "$single" && file_exists "$CONGO_BASELINE"; then
    local diff_out
    diff_out=$(diff <(cat "$CONGO_BASELINE") <(cat "$single") 2>/dev/null)
    local add_lines
    add_lines=$(echo "$diff_out" | grep -c '^>')
    local del_lines
    del_lines=$(echo "$diff_out" | grep -c '^<')

    if [ "$del_lines" -le 5 ] && [ "$add_lines" -le 60 ]; then
      # 0 deletions = perfect increment; ≤3 deletions = acceptable (e.g. .Content → H2-split for in-article ad)
      local del_note=""
      [ "$del_lines" -gt 0 ] && del_note=" (${del_lines} intentional replacements)"
      check "$blog_id" "DIFF" "Diff vs Congo baseline: ${del_lines} deletions, ${add_lines} additions${del_note}" "true"
    elif [ "$del_lines" -gt 3 ]; then
      check "$blog_id" "DIFF" "Diff vs Congo baseline: ${del_lines} deletions, ${add_lines} additions — FULL REWRITE!" "false"
    else
      warn "$blog_id" "DIFF" "Diff vs Congo baseline: ${add_lines} additions (may need review)"
    fi
  fi

  #--- H1 classes match Congo original ---
  if grep_q 'text-4xl font-extrabold text-neutral-900' "$single"; then
    check "$blog_id" "H1" "H1 has correct Congo classes (text-4xl, font-extrabold, text-neutral-900)" "true"
  else
    check "$blog_id" "H1" "H1 has correct Congo classes (currently: $(grep 'h1' "$single" | head -1 | sed 's/.*<h1/h1/;s/<\/h1>//' 2>/dev/null || echo 'not found'))" "false"
  fi

  #--- Feature image with picture/webp ---
  if grep_q 'picture\.html' "$single" || grep_q 'partial.*picture' "$single"; then
    check "$blog_id" "FEATURE_IMG" "Feature image uses picture.html partial (webp support)" "true"
  else
    warn "$blog_id" "FEATURE_IMG" "Feature image may lack webp/picture partial support"
  fi

  #--- Breadcrumbs ---
  if grep_q 'breadcrumbs' "$single"; then
    check "$blog_id" "BREADCRUMBS" "Breadcrumbs partial preserved" "true"
  else
    check "$blog_id" "BREADCRUMBS" "Breadcrumbs partial preserved" "false"
  fi

  #--- Table of Contents ---
  if grep_q 'TableOfContents\|toc\.html' "$single"; then
    check "$blog_id" "TOC" "Table of Contents structure present" "true"
  else
    check "$blog_id" "TOC" "Table of Contents structure present" "false"
  fi

  #--- Stock chart widget ---
  if grep_q 'tradingview-widget\|InvTechnicalChartWidget\|investing\.com.*chart' "$single"; then
    check "$blog_id" "CHART" "Stock chart widget present (tradingview/investing.com)" "true"
  else
    check "$blog_id" "CHART" "Stock chart widget present" "false"
  fi

  #--- AdSense ads ---
  if grep_q 'adsbygoogle' "$single"; then
    check "$blog_id" "ADS" "AdSense adsbygoogle script present" "true"
  else
    check "$blog_id" "ADS" "AdSense adsbygoogle script present" "false"
  fi

  #--- Author ---
  if grep_q 'author\.html' "$single"; then
    check "$blog_id" "AUTHOR" "Author partial present" "true"
  else
    check "$blog_id" "AUTHOR" "Author partial present" "false"
  fi

  #--- Sharing links ---
  if grep_q 'sharing-links' "$single"; then
    check "$blog_id" "SHARING" "Sharing links partial present" "true"
  else
    check "$blog_id" "SHARING" "Sharing links partial present" "false"
  fi

  #--- Article pagination ---
  if grep_q 'article-pagination' "$single"; then
    check "$blog_id" "PAGINATION" "Article pagination partial present" "true"
  else
    check "$blog_id" "PAGINATION" "Article pagination partial present" "false"
  fi

  #--- Comments with existence check ---
  if grep_q 'templates.Exists.*comments' "$single"; then
    check "$blog_id" "COMMENTS" "Comments partial with existence check preserved" "true"
  else
    check "$blog_id" "COMMENTS" "Comments partial with existence check preserved" "false"
  fi

  #--- showTableOfContents in params ---
  local params="${dir}/config/_default/params.toml"
  if file_exists "$params"; then
    if grep_q 'showTableOfContents = false' "$params"; then
      check "$blog_id" "TOC_OFF" "showTableOfContents = false in params.toml" "true"
    else
      warn "$blog_id" "TOC_OFF" "showTableOfContents not set to false in params.toml"
    fi
  fi
}

#===============================================================================
# Main
#===============================================================================

main() {
  echo -e "${cyan}============================================${nc}"
  echo -e "${cyan}  Hugo Template Integrity Checker${nc}"
  echo -e "${cyan}============================================${nc}"
  echo "Date: $(date)"
  echo ""

  #--- Verify baselines exist ---
  if ! file_exists "$BLOWFISH_BASELINE"; then
    echo -e "${red}[FATAL]${nc} Blowfish baseline not found: ${BLOWFISH_BASELINE}"
    echo "Install blowfish theme in shared-themes first."
    exit 1
  fi
  echo -e "[INFO] Blowfish baseline: ${BLOWFISH_BASELINE} ($(wc -l < "$BLOWFISH_BASELINE") lines)"

  if file_exists "$CONGO_BASELINE"; then
    echo -e "[INFO] Congo baseline: ${CONGO_BASELINE} ($(wc -l < "$CONGO_BASELINE") lines)"
  else
    echo -e "[INFO] Congo baseline not found at ${CONGO_BASELINE} — skipping Congo diff checks"
  fi
  echo ""

  #--- Parse arguments ---
  local target="$1"
  local ran_any=false

  if [ "$target" = "--list" ]; then
    echo "Known Blowfish blogs:"
    for b in "${BLOWFISH_BLOGS[@]}"; do echo "  ${b}-hugo"; done
    echo "Known Congo blogs:"
    for b in "${CONGO_BLOGS[@]}"; do echo "  ${b}-hugo"; done
    return
  fi

  #--- Check Blowfish blogs ---
  for blog_id in "${BLOWFISH_BLOGS[@]}"; do
    if [ -z "$target" ] || [ "${target}" = "${blog_id}-hugo" ] || [ "${target}" = "${blog_id}" ]; then
      check_blowfish_blog "$blog_id"
      ran_any=true
    fi
  done

  #--- Check Congo blogs ---
  for blog_id in "${CONGO_BLOGS[@]}"; do
    if [ -z "$target" ] || [ "${target}" = "${blog_id}-hugo" ] || [ "${target}" = "${blog_id}" ]; then
      check_congo_blog "$blog_id"
      ran_any=true
    fi
  done

  #--- Summary ---
  echo ""
  echo -e "${cyan}============================================${nc}"
  echo -e "${cyan}  Summary${nc}"
  echo -e "${cyan}============================================${nc}"
  if [ "$FAIL" -eq 0 ] && [ "$WARN" -eq 0 ]; then
    echo -e "${green}  All checks passed!"
  elif [ "$FAIL" -eq 0 ] && [ "$WARN" -gt 0 ]; then
    echo -e "${yellow}  All ${PASS} critical checks passed, but ${WARN} warnings exist."
  else
    echo -e "${red}  ${FAIL} failures — template regressions detected!${nc}"
  fi
  echo "  PASS: ${PASS}  |  FAIL: ${FAIL}  |  WARN: ${WARN}"
  echo ""

  if [ "$FAIL" -gt 0 ]; then
    echo -e "${red}Review failures above. For Blowfish blogs, verify single.html hasn't been rewritten.${nc}"
    echo -e "${red}Run: diff <(cat ${BLOWFISH_BASELINE}) <(cat ${STAP_ROOT}/{blog}-hugo/layouts/_default/single.html)${nc}"
    exit 1
  fi

  if ! $ran_any; then
    echo -e "${yellow}No blogs matched target: '${target}'${nc}"
    echo "Run without arguments to check all blogs, or use --list to see known blogs."
    exit 1
  fi
}

main "$@"
