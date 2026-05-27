#!/usr/bin/env bash
#
# impact-chain.sh — 影响面调用链分析
#
# 输入: git diff 变更文件列表（stdin，每行一个路径）
# 输出: markdown 格式，向上到入口层、向下到数据层的调用链
#
# 用法:
#   git diff main --name-only | bash impact-chain.sh
#   git diff HEAD~3 --name-only | bash impact-chain.sh --depth 3
#
# 支持: Go · PHP · Java · TypeScript/JavaScript (JSX/TSX)
# 无缓存，每次重建分析。
#
set -euo pipefail

DEPTH="${DEPTH:-2}"
LANG=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --depth) DEPTH="$2"; shift 2 ;;
    --lang)  LANG="$2"; shift 2 ;;
    *) break ;;
  esac
done

# ============================================================================
# 工具函数
# ============================================================================

# 文件级 grep: 从单个文件提取文本（用 rg 或 perl，不用系统 grep -P）
HAS_RG=false
command -v rg &>/dev/null && HAS_RG=true

file_grep() {
  local regex="$1" file="$2"
  if $HAS_RG; then
    rg -oP -r '$1' "$regex" "$file" 2>/dev/null || true
  else
    perl -nle "print \$1 while /${regex}/g" "$file" 2>/dev/null || true
  fi
}

# 全仓反查: 用 git grep（自带 PCRE，所有平台通用）
repo_grep() {
  git grep -P -l "$@" 2>/dev/null || true
}

# 集合操作: 向换行分隔列表中添加元素（去重）
list_contains() {
  printf '%s\n' "$2" | grep -qxF "$1" 2>/dev/null
}
list_add() {
  echo "$1"
}

# ============================================================================
# 语言检测
# ============================================================================
detect_lang() {
  case "${1##*.}" in
    go)                      echo "go" ;;
    php)                     echo "php" ;;
    java)                    echo "java" ;;
    ts|tsx|mts|cts|js|jsx|mjs|cjs) echo "js" ;;
    *)                       echo "" ;;
  esac
}

# ============================================================================
# 层文件匹配
# ============================================================================
is_entry_file() {
  local f="$1"
  # 排除测试文件
  case "$f" in *_test.*|*_test.go|*.spec.*|*.test.*|*Test.*) return 1 ;; esac

  case "$f" in
    # Web 框架: Controller / Handler / Route / Resolver / Resource
    *[Cc]ontroller*|*[Hh]andler*|*[Rr]esource*|*[Rr]outer*|*[Rr]oute*|*[Rr]esolver*)
      return 0 ;;
    */[Cc]ontrollers/*|*/[Hh]andlers/*|*/[Rr]outers/*|*/[Rr]outes/*|*/[Rr]esolvers/*)
      return 0 ;;
    */*[Cc]ontroller.[jt]s*|*/*[Cc]ontroller.php)
      return 0 ;;
    # API 传输层
    */[Aa]pi/*|*/[Hh]ttp/*|*/[Tt]ransport/*|*/[Ww]eb/*|*/[Gg]rpc/*)
      return 0 ;;
    # Go 特定 suffix
    *_grpc.go|*_http.go|*_server.go|*_gateway.go|*_handler.go|*_endpoint.go)
      return 0 ;;
    # JS/TS 工具 / 界面 / 命令 / 入口层
    */tools/*|*/screens/*|*/commands/*|*/entrypoints/*)
      return 0 ;;
    *Tool.ts|*Tool.tsx|*Tool.js|*Screen.tsx|*Screen.jsx)
      return 0 ;;
    # 顶层入口文件
    */main.*|*/index.*|*/app.*|*/server.*|*/bootstrap.*|*/lambda.*)
      return 0 ;;
    *)
      return 1 ;;
  esac
}

is_data_file() {
  local f="$1"
  case "$f" in
    *[Dd]ao*|*[Dd][Aa][Oo]*|*[Rr]epository*|*[Rr]epo*|*[Mm]apper*)
      return 0 ;;
    *[Ss]tore*|*[Mm]odel*|*[Ee]ntity*|*[Pp]ersistence*|*[Oo]rm*|*[Qq]uery*)
      return 0 ;;
    */[Dd]ao/*|*/[Dd]omain/*|*/[Ii]nfrastructure/*|*/[Ii]nfra/*|*/[Dd]ata/*|*/[Dd]b/*)
      return 0 ;;
    */[Rr]epositories/*|*/[Mm]appers/*|*/[Mm]odels/*|*/[Ee]ntities/*|*/[Ss]chemas/*)
      return 0 ;;
    */services/api/*|*/services/http/*|*/services/db/*)
      return 0 ;;
    *Client.ts|*Client.tsx|*Client.js|*Api.ts|*Api.js)
      return 0 ;;
    *)
      return 1 ;;
  esac
}

# ============================================================================
# 符号提取（按语言）
# ============================================================================
extract_go_symbols() {
  local pkg
  pkg=$(file_grep '^package\s+(\w+)' "$1" | head -1)
  [[ -z "$pkg" ]] && return
  file_grep 'func\s+(?:\([^)]*\w+\s+\*?[\w.]+\s*\)\s+)?([A-Z]\w*)' "$1" | while read -r fn; do
    echo "${pkg}.${fn}"
  done
}

extract_php_symbols() {
  local ns cls
  ns=$(file_grep 'namespace\s+([\w\\]+)' "$1" | head -1)
  cls=$(file_grep '(?:class|trait|interface)\s+(\w+)' "$1" | head -1)
  file_grep '(?:public|protected)\s+(?:static\s+)?function\s+(\w+)' "$1" | while read -r m; do
    if [[ -n "$ns" && -n "$cls" ]]; then echo "${ns}\\${cls}::${m}"
    elif [[ -n "$ns" ]]; then echo "${ns}\\${m}"
    else echo "${m}"; fi
  done
}

extract_java_symbols() {
  local pkg cls
  pkg=$(file_grep 'package\s+([\w.]+)' "$1" | head -1)
  cls=$(file_grep '(?:public\s+)?(?:abstract\s+)?(?:class|interface|enum)\s+(\w+)' "$1" | head -1)
  file_grep '(?:public|protected)\s+(?:static\s+)?(?:\w+(?:<[^>]+>)?\s+)+(\w+)(?=\s*\()' "$1" | while read -r m; do
    if [[ -n "$pkg" && -n "$cls" ]]; then echo "${pkg}.${cls}#${m}"
    elif [[ -n "$cls" ]]; then echo "${cls}#${m}"
    else echo "${m}"; fi
  done
}

extract_js_symbols() {
  # export function / const / class / default
  file_grep 'export\s+(?:default\s+)?(?:async\s+)?(?:function|const|let|var|class|interface|type|enum)\s+(\w+)' "$1"
  # export { foo, bar }
  file_grep "export\s+\{\s*([^}]+)\s*\}" "$1" | tr ',' '\n' | sed 's/^\s*//;s/\s*$//' | grep -v '^$' || true
}

# ============================================================================
# 调用追踪
# ============================================================================
search_callers() {
  local sym="$1" lang="$2" short
  case "$lang" in
    go)
      short=$(echo "$sym" | rev | cut -d. -f1 | rev)
      repo_grep -l "\b${short}\b" -- '*.go'
      ;;
    php)
      local sm sc
      sm=$(echo "$sym" | rev | cut -d: -f1 | rev | rev | cut -d\\ -f1 | rev)
      sc=$(echo "$sym" | rev | cut -d: -f2- | rev | rev | cut -d\\ -f1 | rev 2>/dev/null || true)
      [[ -n "$sc" ]] && repo_grep -l "\b${sc}::${sm}\b" -- '*.php'
      repo_grep -l "\b${sm}\b" -- '*.php'
      ;;
    java)
      short=$(echo "$sym" | rev | cut -d'#' -f1 | rev | cut -d. -f1 | rev)
      repo_grep -l "\b${sym%#*}\b" -- '*.java'
      repo_grep -l "\b${short}\b" -- '*.java'
      ;;
    js)
      short="${sym##*.}"
      [[ "$short" == "$sym" ]] || true  # 保持原样
      repo_grep -l "\b${short}\b" -- '*.ts' '*.tsx' '*.js' '*.jsx' '*.mjs' '*.mts'
      ;;
  esac
}

find_downstream_calls() {
  local file="$1" lang="$2"
  case "$lang" in
    go)
      file_grep '(?:repo|Repo|dao|DAO|Dao|store|Store|model|Model|db|DB)\.(\w+)' "$file" | sort -u
      ;;
    php)
      file_grep '\b(\w*(?:Dao|DAO|Repository|Repo|Mapper|Store|Model))\b' "$file" | sort -u
      ;;
    java)
      file_grep '\b(\w*(?:Dao|DAO|Repository|Repo|Mapper|Store|Model))\b' "$file" | sort -u
      ;;
    js)
      file_grep "from\s+['\"]([^'\"]*(?:service|api|client|repository|store|db|dao|repo)[^'\"]*)['\"]" "$file" | sort -u
      file_grep "require\s*\(\s*['\"]([^'\"]*(?:service|api|client|repository|store|db|dao|repo)[^'\"]*)['\"]\s*\)" "$file" | sort -u
      ;;
  esac
}

# ============================================================================
# 主流程
# ============================================================================
changed_files=$(cat | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | grep -v '^$' || true)

if [[ -z "$changed_files" ]]; then
  echo "## 影响面调用链分析"
  echo ""
  echo "_(无变更文件输入。通过管道传入 git diff 文件列表。)_"
  exit 0
fi

echo "## 影响面调用链分析"
echo ""

seen=""

while IFS= read -r file; do
  lang="${LANG:-$(detect_lang "$file")}"
  [[ -z "$lang" ]] && continue
  [[ ! -f "$file" ]] && continue

  # 去重
  if echo "$seen" | grep -qxF "$file" 2>/dev/null; then continue; fi
  seen="${seen}${file}"$'\n'

  echo "### \`$file\`"

  # ── 提取符号 ──
  case "$lang" in
    go)   symbols=$(extract_go_symbols "$file") ;;
    php)  symbols=$(extract_php_symbols "$file") ;;
    java) symbols=$(extract_java_symbols "$file") ;;
    js)   symbols=$(extract_js_symbols "$file") ;;
    *)    symbols="" ;;
  esac

  up_list=""
  down_list=""

  # ── 向上：发现调用者 → 筛出入口层 ──
  if [[ -n "$symbols" ]]; then
    while IFS= read -r sym; do
      [[ -z "$sym" ]] && continue
      callers=$(search_callers "$sym" "$lang" | sort -u || true)
      for caller in $callers; do
        [[ "$caller" == "$file" ]] && continue
        echo "$up_list" | grep -qxF "$caller" 2>/dev/null && continue
        if is_entry_file "$caller"; then
          up_list="${up_list}${caller}"$'\n'
        fi
      done
    done <<< "$symbols"
  fi

  up_count=$(echo "$up_list" | grep -c . 2>/dev/null || echo 0)
  if [[ "$up_count" -gt 0 ]]; then
    echo ""
    echo "**📡 向上 → 入口层:**"
    echo "$up_list" | grep -v '^$' | sort -u | while read -r f; do
      echo "  - \`$f\`"
    done
  fi

  # ── 向下：找数据层依赖 ──
  downstream=$(find_downstream_calls "$file" "$lang")
  if [[ -n "$downstream" ]]; then
    while IFS= read -r dep; do
      [[ -z "$dep" ]] && continue
      echo "$down_list" | grep -qxF "$dep" 2>/dev/null && continue
      down_list="${down_list}${dep}"$'\n'
    done <<< "$downstream"
  fi

  # import/use 语句补充
  case "$lang" in
    php)
      file_grep 'use\s+([\w\\]+(?:Dao|DAO|Repository|Repo|Mapper|Store))\b' "$file" | while read -r imp; do
        down_list="${down_list}${imp}"$'\n'
      done
      ;;
    java)
      file_grep 'import\s+([\w.]+(?:Dao|DAO|Repository|Repo|Mapper|Store))\b' "$file" | while read -r imp; do
        down_list="${down_list}${imp}"$'\n'
      done
      ;;
    go)
      file_grep '"([\w./]+\b(?:repo|dao|store|model)[\w.]*)"' "$file" | while read -r imp; do
        down_list="${down_list}${imp}"$'\n'
      done
      ;;
    js)
      file_grep "from\s+['\"]([^'\"]*(?:Dao|DAO|Repository|Repo|Mapper|Store|Model|Entity)[^'\"]*)['\"]" "$file" | while read -r imp; do
        down_list="${down_list}${imp}"$'\n'
      done
      ;;
  esac

  down_count=$(echo "$down_list" | grep -c . 2>/dev/null || echo 0)
  if [[ "$down_count" -gt 0 ]]; then
    echo ""
    echo "**🗄️ 向下 → 数据 / 服务层:**"
    echo "$down_list" | grep -v '^$' | sort -u | while read -r dep; do
      echo "  - \`$dep\`"
    done
  fi

  if [[ "$up_count" -eq 0 && "$down_count" -eq 0 ]]; then
    echo "  _(未发现明显的入口层或数据层依赖)_"
  fi

  echo ""
done <<< "$changed_files"

echo "---"
echo "*分析深度: ${DEPTH} · 变更文件数: $(echo "$changed_files" | wc -l | tr -d ' ')*"
