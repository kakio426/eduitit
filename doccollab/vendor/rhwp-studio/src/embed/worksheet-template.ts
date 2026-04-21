import type { WasmBridge } from '@/core/wasm-bridge';


function normalizeText(value: unknown): string {
  return String(value || '').replace(/\r\n/g, '\n').trim();
}

function answerLines(count: number): string {
  const lines = Math.max(1, Math.min(Number(count || 1), 2));
  return Array.from({ length: lines }, () => '____________________________').join('\n');
}

function quizText(item: Record<string, unknown> | null): string {
  if (!item) {
    return '';
  }
  const prompt = normalizeText(item.prompt);
  if (!prompt) {
    return '';
  }
  return [prompt, answerLines(Number(item.answer_lines || 1))].join('\n');
}

function replaceToken(wasm: WasmBridge, token: string, value: string): void {
  wasm.replaceAll(token, value, true);
}

export function fillWorksheetTemplate(
  wasm: WasmBridge,
  content: Record<string, unknown>,
  layoutProfile: string,
): { pageCount: number; appliedProfile: string; overflow: boolean } {
  const keyPoints = Array.isArray(content.key_points) ? content.key_points : [];
  const quizItems = Array.isArray(content.quiz_items) ? content.quiz_items : [];
  replaceToken(wasm, '[[TITLE]]', normalizeText(content.title));
  replaceToken(wasm, '[[COMPANION]]', normalizeText(content.companion_line));
  replaceToken(wasm, '[[OPENING]]', normalizeText(content.curiosity_opening));
  replaceToken(wasm, '[[KEYPOINT_1]]', normalizeText(keyPoints[0]));
  replaceToken(wasm, '[[KEYPOINT_2]]', normalizeText(keyPoints[1]));
  replaceToken(wasm, '[[KEYPOINT_3]]', normalizeText(keyPoints[2]));
  replaceToken(wasm, '[[QUIZ_1]]', quizText((quizItems[0] || null)));
  replaceToken(wasm, '[[QUIZ_2]]', quizText((quizItems[1] || null)));
  const fileTitle = normalizeText(content.title) || 'worksheet';
  wasm.fileName = `${fileTitle}.hwp`;
  const pageCount = wasm.pageCount;
  return {
    pageCount,
    appliedProfile: layoutProfile,
    overflow: pageCount > 1,
  };
}
