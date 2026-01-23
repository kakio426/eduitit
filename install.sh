#!/bin/bash

# Claude Code Configuration Installer
# https://github.com/jh941213/my-claude-code-asset

set -e

echo "🚀 Claude Code 설정 설치 시작..."

# 임시 디렉토리에 클론
TEMP_DIR=$(mktemp -d)
git clone --depth 1 https://github.com/jh941213/my-claude-code-asset.git "$TEMP_DIR"

# ~/.claude 디렉토리 생성
mkdir -p ~/.claude/agents ~/.claude/commands ~/.claude/rules

# 파일 복사
echo "📁 설정 파일 복사 중..."

cp "$TEMP_DIR/CLAUDE.md" ~/.claude/
cp "$TEMP_DIR/settings.json" ~/.claude/
cp "$TEMP_DIR/agents/"*.md ~/.claude/agents/
cp "$TEMP_DIR/commands/"*.md ~/.claude/commands/
cp "$TEMP_DIR/rules/"*.md ~/.claude/rules/

# 정리
rm -rf "$TEMP_DIR"

echo ""
echo "✅ 설치 완료!"
echo ""
echo "📂 설치된 위치: ~/.claude/"
echo ""
echo "📋 설치된 항목:"
echo "   - CLAUDE.md (전역 설정)"
echo "   - settings.json (권한/Hooks)"
echo "   - agents/ (5개 에이전트)"
echo "   - commands/ (9개 커맨드)"
echo "   - rules/ (5개 규칙)"
echo ""
echo "🎯 사용 가능한 커맨드:"
echo "   /plan, /verify, /commit-push-pr, /review"
echo "   /simplify, /tdd, /build-fix, /handoff"
echo ""
echo "💡 터미널 alias 추가하려면:"
echo '   echo '\''alias c="claude"'\'' >> ~/.zshrc && source ~/.zshrc'
echo ""
