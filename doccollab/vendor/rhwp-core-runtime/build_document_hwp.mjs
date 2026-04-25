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

const FONT_FAMILY = "함초롬바탕";
const FONT_FAMILIES = Array(7).fill(FONT_FAMILY);
const SPACINGS = Array(7).fill(0);
const RATIOS = Array(7).fill(100);
const RELATIVE_SIZES = Array(7).fill(100);
const CHAR_OFFSETS = Array(7).fill(0);

const DOCUMENT_STYLE = {
  titleSize: 1700,
  subtitleSize: 1080,
  headingSize: 1180,
  infoSize: 1060,
  bodySize: 1080,
  closingSize: 1060,
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
