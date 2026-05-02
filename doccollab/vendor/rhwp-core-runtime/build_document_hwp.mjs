import fs from "node:fs";
import path from "node:path";
import process from "node:process";

import initRhwp, { HwpDocument } from "./rhwp.js";


const PAGE_DEF = {
  width: 59528,
  height: 84186,
  marginLeft: 5669,
  marginRight: 5669,
  marginTop: 4252,
  marginBottom: 4252,
  marginHeader: 2835,
  marginFooter: 2835,
  marginGutter: 0,
  landscape: false,
  binding: 0,
};

const DOCUMENT_SPEC_VERSION = "document-spec-v2";
const BODY_FONT_FAMILY = "함초롬바탕";
const TABLE_FONT_FAMILY = "함초롬돋움";
const FONT_FAMILY = BODY_FONT_FAMILY;
const FONT_FAMILIES = Array(7).fill(FONT_FAMILY);
const TABLE_FONT_FAMILIES = Array(7).fill(TABLE_FONT_FAMILY);
const SPACINGS = Array(7).fill(0);
const RATIOS = Array(7).fill(100);
const RELATIVE_SIZES = Array(7).fill(100);
const CHAR_OFFSETS = Array(7).fill(0);
const TABLE_BLOCK_TYPES = new Set(["meta_table", "info_table", "schedule_table", "decision_table", "budget_table"]);

const DOCUMENT_STYLE = {
  titleSize: 1700,
  subtitleSize: 1050,
  headingSize: 1200,
  infoSize: 950,
  bodySize: 1050,
  closingSize: 1050,
  tableSize: 950,
  titleAfter: 10.7,
  subtitleAfter: 8.0,
  headingAfter: 8.0,
  infoAfter: 9.3,
  bodyAfter: 6.7,
  closingAfter: 8.0,
};

const PARA_GROUPS = {
  title: [0],
  subtitle: [1],
  heading: [2, 4, 8],
  info: [3],
  body: [5, 6, 7],
  closing: [9, 10],
};


globalThis.measureTextWidth = (_font, text) => {
  const value = String(text || "");
  let width = 0;
  for (const char of value) {
    width += estimateCharWidth(char);
  }
  return Math.max(width, 1);
};


async function main() {
  const [, , inputPath, outputPath] = process.argv;
  if (!inputPath || !outputPath) {
    throw new Error("usage: node build_document_hwp.mjs <input.json> <output.hwpx>");
  }

  const runtimeDir = path.dirname(new URL(import.meta.url).pathname);
  const wasmBytes = fs.readFileSync(path.join(runtimeDir, "rhwp_bg.wasm"));
  await initRhwp({ module_or_path: wasmBytes });

  const request = JSON.parse(fs.readFileSync(inputPath, "utf8"));
  const doc = new HwpDocument(
    new Uint8Array(fs.readFileSync(String(request.templatePath))),
  );

  applyPageDef(doc);
  fillTemplateText(doc, request.content || {});
  applyDocumentStyles(doc);

  const pageCount = Math.max(Number(doc.pageCount() || 0), 0);
  const fileName = ensureHwpxFileName(request.title || "document");
  doc.setFileName?.(fileName);
  fs.writeFileSync(outputPath, Buffer.from(doc.exportHwpx()));
  process.stdout.write(`${JSON.stringify({ pageCount, fileName })}\n`);
}


function estimateCharWidth(char) {
  if (!char) {
    return 0;
  }
  const code = char.codePointAt(0) || 0;
  if (/\s/.test(char)) {
    return 4;
  }
  if (/[.,'`:;!|]/.test(char)) {
    return 4.2;
  }
  if (/[ilI1\[\]\(\)]/.test(char)) {
    return 5.1;
  }
  if (/[MW@#%&]/.test(char)) {
    return 8.4;
  }
  if ((code >= 0x3131 && code <= 0x318e) || (code >= 0xac00 && code <= 0xd7a3) || (code >= 0x4e00 && code <= 0x9fff)) {
    return 10.4;
  }
  return 6.8;
}


function ensureHwpxFileName(value) {
  const stem = String(value || "document")
    .replace(/[\\/:*?"<>|]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 80) || "document";
  return stem.toLowerCase().endsWith(".hwpx") ? stem : `${stem.replace(/\.[^.]+$/u, "")}.hwpx`;
}


function applyPageDef(doc) {
  const result = JSON.parse(doc.setPageDef(0, JSON.stringify(PAGE_DEF)));
  if (!result?.ok) {
    throw new Error("page definition update failed");
  }
}


function fillTemplateText(doc, content) {
  if (content?.schema_version === DOCUMENT_SPEC_VERSION && Array.isArray(content.blocks)) {
    fillSpecTemplateText(doc, content);
    return;
  }

  const bodySlots = buildBodySlots(content.body_blocks || []);
  const metaText = buildMetaText(content);
  const replacements = [
    ["[[TITLE]]", cleanLine(content.title) || "문서 초안"],
    ["[[COMPANION]]", cleanLine(content.subtitle) || "AI 문서 초안"],
    ["호기심 열기 ☆", "문서 정보"],
    ["[[OPENING]]", metaText],
    ["핵심 쏙쏙 ♡", "본문"],
    ["• [[KEYPOINT_1]]", bodySlots[0] || ""],
    ["• [[KEYPOINT_2]]", bodySlots[1] || ""],
    ["• [[KEYPOINT_3]]", bodySlots[2] || ""],
    ["내 생각 키우기 ♪", "마무리"],
    ["1. [[QUIZ_1]]", buildClosingText(content)],
    ["2. [[QUIZ_2]]", ""],
  ];

  for (const [search, replace] of replacements) {
    const result = JSON.parse(doc.replaceAll(search, replace));
    if (!result?.ok) {
      throw new Error(`replace failed: ${search}`);
    }
  }
}


function fillSpecTemplateText(doc, content) {
  const plan = buildSpecRenderPlan(content);
  const replacements = [
    ["[[TITLE]]", plan.title || "문서 초안"],
    ["[[COMPANION]]", plan.subtitle || "학교 실무 문서"],
    ["호기심 열기 ☆", "문서 정보"],
    ["[[OPENING]]", plan.metaText],
    ["핵심 쏙쏙 ♡", "본문"],
    ["• [[KEYPOINT_1]]", plan.bodySlots[0] || ""],
    ["• [[KEYPOINT_2]]", plan.bodySlots[1] || ""],
    ["• [[KEYPOINT_3]]", plan.bodySlots[2] || ""],
    ["내 생각 키우기 ♪", "확인"],
    ["1. [[QUIZ_1]]", plan.closingText],
    ["2. [[QUIZ_2]]", ""],
  ];

  for (const [search, replace] of replacements) {
    const result = JSON.parse(doc.replaceAll(search, replace));
    if (!result?.ok) {
      throw new Error(`replace failed: ${search}`);
    }
  }
  // Newly created rhwp table controls are not serialized by exportHwpx in this runtime.
  // Django injects HWPX table XML after export so table data is preserved in the file.
}


function buildSpecRenderPlan(content) {
  const blocks = Array.isArray(content.blocks) ? content.blocks : [];
  const masthead = blocks.find((block) => block?.type === "masthead") || {};
  const titleBlock = blocks.find((block) => block?.type === "title") || {};
  const signatureBlock = [...blocks].reverse().find((block) => block?.type === "signature_box") || null;
  const metaBlocks = blocks.filter((block) => block?.type === "meta_table");
  const contentBlocks = blocks.filter((block) => !["masthead", "title", "meta_table", "signature_box"].includes(block?.type));
  const tableBlocks = blocks.filter((block) => TABLE_BLOCK_TYPES.has(block?.type));
  const bodyEntries = contentBlocks.map((block) => renderSpecBlock(block)).filter(Boolean);

  return {
    title: cleanLine(titleBlock.text || content.title),
    subtitle: cleanLine(titleBlock.subtitle || content.subtitle || ""),
    metaText: renderMasthead(masthead, metaBlocks),
    bodySlots: distributeEntries(bodyEntries),
    closingText: renderSignature(signatureBlock) || "20  .  .\n○○학교장",
    tableBlocks,
  };
}


function renderMasthead(masthead, metaBlocks) {
  const lines = [];
  const schoolName = cleanLine(masthead.school_name || "○○학교");
  const department = cleanLine(masthead.department || "");
  const contact = cleanLine(masthead.contact || "교무실 000-0000-0000");
  const fax = cleanLine(masthead.fax || "");
  lines.push(`${schoolName}${department ? ` · ${department}` : ""}`);
  if (contact) lines.push(`문의: ${contact}`);
  if (fax) lines.push(`FAX: ${fax}`);
  for (const block of metaBlocks.slice(0, 1)) {
    const headers = normalizeHeaders(block.headers);
    const rows = normalizeRows(block.rows, headers).slice(0, 6);
    for (const row of rows) {
      lines.push(`${row[0]}: ${row.slice(1).join(" / ")}`);
    }
  }
  return lines.join("\n");
}


function renderSpecBlock(block) {
  const type = block?.type;
  if (!type) return "";
  if (type === "paragraph") {
    const title = cleanLine(block.title || "");
    const text = cleanLine(block.text || "");
    return [title, text].filter(Boolean).join("\n");
  }
  if (type === "bullet_list") {
    const title = cleanLine(block.title || "확인 사항");
    const items = Array.isArray(block.items) ? block.items.map((item) => cleanLine(item)).filter(Boolean) : [];
    return [title, ...items.map((item) => `- ${item}`)].join("\n");
  }
  if (TABLE_BLOCK_TYPES.has(type)) {
    return cleanLine(block.title || "표");
  }
  if (type === "callout_box") {
    const title = cleanLine(block.title || "확인");
    const text = cleanLine(block.text || "");
    return [`[${title}]`, text].filter(Boolean).join("\n");
  }
  return "";
}


function distributeEntries(entries) {
  const size = Math.max(Math.ceil(entries.length / 3), 1);
  return [
    entries.slice(0, size).join("\n\n"),
    entries.slice(size, size * 2).join("\n\n"),
    entries.slice(size * 2, size * 3).join("\n\n"),
  ];
}


function renderSignature(block) {
  if (!block) return "";
  return [
    cleanLine(block.date || "20  .  ."),
    cleanLine(block.signer || "○○학교장"),
    cleanLine(block.note || ""),
  ].filter(Boolean).join("\n");
}


function applySpecTables(doc, tableBlocks) {
  const anchors = [3, 5, 6, 7];
  for (const [index, block] of tableBlocks.slice(0, anchors.length).entries()) {
    const anchorPara = anchors[index];
    const headers = normalizeHeaders(block.headers);
    const rows = normalizeRows(block.rows, headers).slice(0, 8);
    if (!headers.length || !rows.length) continue;
    const created = JSON.parse(doc.createTable(0, anchorPara, 0, rows.length + 1, headers.length));
    if (!created?.ok) {
      throw new Error(`table create failed: ${block.type || index}`);
    }
    headers.forEach((header, columnIndex) => {
      insertCellText(doc, created.paraIdx, created.controlIdx, columnIndex, header);
      applyCellTextStyle(doc, created.paraIdx, created.controlIdx, columnIndex, true, "center");
    });
    rows.forEach((row, rowIndex) => {
      row.forEach((cell, columnIndex) => {
        const cellIndex = (rowIndex + 1) * headers.length + columnIndex;
        insertCellText(doc, created.paraIdx, created.controlIdx, cellIndex, cell);
        applyCellTextStyle(doc, created.paraIdx, created.controlIdx, cellIndex, false, columnIndex === 0 ? "center" : "left");
      });
    });
  }
}


function normalizeHeaders(value) {
  const headers = Array.isArray(value) ? value.map((item) => cleanLine(item)).filter(Boolean).slice(0, 5) : [];
  return headers.length ? headers : ["항목", "내용"];
}


function normalizeRows(value, headers) {
  const rows = Array.isArray(value) ? value : [];
  return rows.map((row) => {
    const cells = Array.isArray(row) ? row : [row];
    const normalized = cells.slice(0, headers.length).map((cell) => cleanLine(cell).slice(0, 110) || "확인 필요");
    while (normalized.length < headers.length) normalized.push("확인 필요");
    return normalized;
  }).filter((row) => row.length);
}


function insertCellText(doc, parentParaIdx, controlIdx, cellIdx, text) {
  const result = JSON.parse(doc.insertTextInCell(0, parentParaIdx, controlIdx, cellIdx, 0, 0, cleanLine(text)));
  if (!result?.ok) {
    throw new Error(`cell text failed: ${parentParaIdx}/${cellIdx}`);
  }
}


function applyCellTextStyle(doc, parentParaIdx, controlIdx, cellIdx, bold, alignment) {
  try {
    const current = JSON.parse(doc.getCellCharPropertiesAt(0, parentParaIdx, controlIdx, cellIdx, 0, 0));
    const charResult = JSON.parse(
      doc.applyCharFormatInCell(
        0,
        parentParaIdx,
        controlIdx,
        cellIdx,
        0,
        0,
        65535,
        JSON.stringify({
          ...current,
          fontSize: DOCUMENT_STYLE.tableSize,
          bold,
          fontFamily: TABLE_FONT_FAMILY,
          fontFamilies: TABLE_FONT_FAMILIES,
          spacings: SPACINGS,
          ratios: RATIOS,
          relativeSizes: RELATIVE_SIZES,
          charOffsets: CHAR_OFFSETS,
        }),
      ),
    );
    if (!charResult?.ok) throw new Error("cell char format failed");
    const paraResult = JSON.parse(
      doc.applyParaFormatInCell(
        0,
        parentParaIdx,
        controlIdx,
        cellIdx,
        0,
        JSON.stringify({
          alignment,
          lineSpacing: 150,
          lineSpacingType: "Percent",
        }),
      ),
    );
    if (!paraResult?.ok) throw new Error("cell para format failed");
  } catch {
    // Cell styling is best-effort; the table and text are the critical output.
  }
}


function buildMetaText(content) {
  const lines = Array.isArray(content.meta_lines) ? content.meta_lines : [];
  const cleanLines = lines.map((line) => cleanLine(line)).filter(Boolean).slice(0, 6);
  return cleanLines.length ? cleanLines.join("\n") : "작성일: \n대상: ";
}


function buildBodySlots(blocks) {
  const normalizedBlocks = Array.isArray(blocks) ? blocks : [];
  const rendered = normalizedBlocks.map((block) => renderBlock(block)).filter(Boolean);
  if (!rendered.length) {
    return ["요청한 내용을 바탕으로 문서 초안을 정리했습니다."];
  }
  return [
    rendered.slice(0, 2).join("\n\n"),
    rendered.slice(2, 5).join("\n\n"),
    rendered.slice(5, 8).join("\n\n"),
  ];
}


function renderBlock(block) {
  const heading = cleanLine(block?.heading || "");
  const paragraphs = Array.isArray(block?.paragraphs) ? block.paragraphs : [];
  const bullets = Array.isArray(block?.bullets) ? block.bullets : [];
  const lines = [];
  if (heading) {
    lines.push(heading);
  }
  for (const paragraph of paragraphs.slice(0, 3)) {
    const text = cleanLine(paragraph);
    if (text) {
      lines.push(text);
    }
  }
  for (const bullet of bullets.slice(0, 5)) {
    const text = cleanLine(bullet);
    if (text) {
      lines.push(`- ${text}`);
    }
  }
  return lines.join("\n");
}


function buildClosingText(content) {
  const closing = cleanLine(content.closing);
  if (closing) {
    return closing;
  }
  const summary = cleanLine(content.summary_text);
  return summary || "위 내용으로 진행합니다.";
}


function cleanLine(value) {
  return String(value || "")
    .replace(/\r/g, "\n")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}


function applyDocumentStyles(doc) {
  for (const paraIndex of PARA_GROUPS.title) {
    applyParaStyle(doc, paraIndex, {
      alignment: "center",
      lineSpacing: 160,
      lineSpacingType: "Percent",
      spacingAfter: DOCUMENT_STYLE.titleAfter,
    });
    applyCharStyle(doc, paraIndex, {
      fontSize: DOCUMENT_STYLE.titleSize,
      bold: true,
    });
  }

  for (const paraIndex of PARA_GROUPS.subtitle) {
    applyParaStyle(doc, paraIndex, {
      alignment: "center",
      lineSpacing: 160,
      lineSpacingType: "Percent",
      spacingAfter: DOCUMENT_STYLE.subtitleAfter,
    });
    applyCharStyle(doc, paraIndex, {
      fontSize: DOCUMENT_STYLE.subtitleSize,
      bold: false,
    });
  }

  for (const paraIndex of PARA_GROUPS.heading) {
    applyParaStyle(doc, paraIndex, {
      alignment: "left",
      lineSpacing: 160,
      lineSpacingType: "Percent",
      spacingAfter: DOCUMENT_STYLE.headingAfter,
    });
    applyCharStyle(doc, paraIndex, {
      fontSize: DOCUMENT_STYLE.headingSize,
      bold: true,
    });
  }

  for (const paraIndex of PARA_GROUPS.info) {
    applyParaStyle(doc, paraIndex, {
      alignment: "left",
      lineSpacing: 160,
      lineSpacingType: "Percent",
      spacingAfter: DOCUMENT_STYLE.infoAfter,
    });
    applyCharStyle(doc, paraIndex, {
      fontSize: DOCUMENT_STYLE.infoSize,
      bold: false,
    });
  }

  for (const paraIndex of PARA_GROUPS.body) {
    applyParaStyle(doc, paraIndex, {
      alignment: "justify",
      lineSpacing: 170,
      lineSpacingType: "Percent",
      spacingAfter: DOCUMENT_STYLE.bodyAfter,
    });
    applyCharStyle(doc, paraIndex, {
      fontSize: DOCUMENT_STYLE.bodySize,
      bold: false,
    });
  }

  for (const paraIndex of PARA_GROUPS.closing) {
    applyParaStyle(doc, paraIndex, {
      alignment: "justify",
      lineSpacing: 170,
      lineSpacingType: "Percent",
      spacingAfter: DOCUMENT_STYLE.closingAfter,
    });
    applyCharStyle(doc, paraIndex, {
      fontSize: DOCUMENT_STYLE.closingSize,
      bold: false,
    });
  }
}


function applyParaStyle(doc, paraIndex, patch) {
  const current = JSON.parse(doc.getParaPropertiesAt(0, paraIndex));
  const result = JSON.parse(
    doc.applyParaFormat(
      0,
      paraIndex,
      JSON.stringify({
        ...current,
        ...patch,
      }),
    ),
  );
  if (!result?.ok) {
    throw new Error(`paragraph format failed: ${paraIndex}`);
  }
}


function applyCharStyle(doc, paraIndex, patch) {
  const current = JSON.parse(doc.getCharPropertiesAt(0, paraIndex, 0));
  const nextProps = {
    ...current,
    ...patch,
    fontFamily: FONT_FAMILY,
    fontFamilies: FONT_FAMILIES,
    spacings: SPACINGS,
    ratios: RATIOS,
    relativeSizes: RELATIVE_SIZES,
    charOffsets: CHAR_OFFSETS,
  };
  const result = JSON.parse(
    doc.applyCharFormat(0, paraIndex, 0, 65535, JSON.stringify(nextProps)),
  );
  if (!result?.ok) {
    throw new Error(`character format failed: ${paraIndex}`);
  }
}


main().catch((error) => {
  const message = error instanceof Error ? error.message : String(error || "document build failed");
  process.stderr.write(`${message}\n`);
  process.exit(1);
});
