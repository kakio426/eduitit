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
const SPACINGS = Array(7).fill(-5);
const RATIOS = Array(7).fill(100);
const RELATIVE_SIZES = Array(7).fill(100);
const CHAR_OFFSETS = Array(7).fill(0);

const PROFILE_STYLES = {
  comfortable: {
    titleSize: 1800,
    companionSize: 1120,
    headingSize: 1220,
    openingSize: 1200,
    keyPointSize: 1160,
    quizSize: 1140,
    titleAfter: 10.7,
    companionAfter: 9.3,
    headingAfter: 9.3,
    openingAfter: 10.7,
    keyPointAfter: 5.3,
    quizAfter: 9.3,
  },
  compact: {
    titleSize: 1700,
    companionSize: 1080,
    headingSize: 1180,
    openingSize: 1140,
    keyPointSize: 1100,
    quizSize: 1080,
    titleAfter: 9.3,
    companionAfter: 8.0,
    headingAfter: 8.0,
    openingAfter: 9.3,
    keyPointAfter: 4.0,
    quizAfter: 8.0,
  },
  tight: {
    titleSize: 1600,
    companionSize: 1040,
    headingSize: 1140,
    openingSize: 1100,
    keyPointSize: 1060,
    quizSize: 1040,
    titleAfter: 8.0,
    companionAfter: 6.7,
    headingAfter: 6.7,
    openingAfter: 8.0,
    keyPointAfter: 2.7,
    quizAfter: 6.7,
  },
};

const PARA_GROUPS = {
  title: [0],
  companion: [1],
  heading: [2, 4, 8],
  opening: [3],
  keyPoint: [5, 6, 7],
  quiz: [9, 10],
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
    throw new Error("usage: node build_worksheet_hwp.mjs <input.json> <output.hwp>");
  }

  const runtimeDir = path.dirname(new URL(import.meta.url).pathname);
  const wasmBytes = fs.readFileSync(path.join(runtimeDir, "rhwp_bg.wasm"));
  await initRhwp({ module_or_path: wasmBytes });

  const request = JSON.parse(fs.readFileSync(inputPath, "utf8"));
  const layoutProfile = String(request.layoutProfile || "comfortable");
  const styleProfile = PROFILE_STYLES[layoutProfile];
  if (!styleProfile) {
    throw new Error("unsupported layout profile");
  }

  const doc = new HwpDocument(
    new Uint8Array(fs.readFileSync(String(request.templatePath))),
  );

  applyPageDef(doc);
  fillTemplateText(doc, request.content || {});
  applyProfileStyles(doc, styleProfile);

  const pageCount = Math.max(Number(doc.pageCount() || 0), 0);
  const fileName = ensureHwpFileName(request.title || "worksheet");
  fs.writeFileSync(outputPath, Buffer.from(doc.exportHwp(fileName)));
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


function ensureHwpFileName(value) {
  const stem = String(value || "worksheet")
    .replace(/[\\/:*?"<>|]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 80) || "worksheet";
  return stem.toLowerCase().endsWith(".hwp") ? stem : `${stem}.hwp`;
}


function applyPageDef(doc) {
  const result = JSON.parse(doc.setPageDef(0, JSON.stringify(PAGE_DEF)));
  if (!result?.ok) {
    throw new Error("page definition update failed");
  }
}


function fillTemplateText(doc, content) {
  const keyPoints = Array.isArray(content.key_points) ? content.key_points : [];
  const quizItems = Array.isArray(content.quiz_items) ? content.quiz_items : [];
  const replacements = [
    ["[[TITLE]]", String(content.title || "").trim()],
    ["[[COMPANION]]", String(content.companion_line || "").trim()],
    ["[[OPENING]]", String(content.curiosity_opening || "").trim()],
    ["• [[KEYPOINT_1]]", buildKeyPointLine(keyPoints[0])],
    ["• [[KEYPOINT_2]]", buildKeyPointLine(keyPoints[1])],
    ["• [[KEYPOINT_3]]", buildKeyPointLine(keyPoints[2])],
    ["1. [[QUIZ_1]]", buildQuizLine(quizItems[0], 1)],
    ["2. [[QUIZ_2]]", buildQuizLine(quizItems[1], 2)],
  ];

  for (const [search, replace] of replacements) {
    const result = JSON.parse(doc.replaceAll(search, replace));
    if (!result?.ok) {
      throw new Error(`replace failed: ${search}`);
    }
  }
}


function buildKeyPointLine(value) {
  const text = String(value || "").trim();
  return text ? `• ${text}` : "";
}


function buildQuizLine(item, order) {
  const prompt = String(item?.prompt || "").trim();
  if (!prompt) {
    return "";
  }
  const answerLines = Number(item?.answer_lines || 1) >= 2 ? 2 : 1;
  const extraLines = answerLines > 1 ? "\n_____" : "";
  return `${order}. ${prompt}${extraLines}`;
}


function applyProfileStyles(doc, profile) {
  for (const paraIndex of PARA_GROUPS.title) {
    applyParaStyle(doc, paraIndex, {
      alignment: "center",
      lineSpacing: 160,
      lineSpacingType: "Percent",
      spacingAfter: profile.titleAfter,
    });
    applyCharStyle(doc, paraIndex, {
      fontSize: profile.titleSize,
      bold: true,
    });
  }

  for (const paraIndex of PARA_GROUPS.companion) {
    applyParaStyle(doc, paraIndex, {
      alignment: "center",
      lineSpacing: 160,
      lineSpacingType: "Percent",
      spacingAfter: profile.companionAfter,
    });
    applyCharStyle(doc, paraIndex, {
      fontSize: profile.companionSize,
      bold: false,
    });
  }

  for (const paraIndex of PARA_GROUPS.heading) {
    applyParaStyle(doc, paraIndex, {
      alignment: "left",
      lineSpacing: 160,
      lineSpacingType: "Percent",
      spacingAfter: profile.headingAfter,
    });
    applyCharStyle(doc, paraIndex, {
      fontSize: profile.headingSize,
      bold: true,
    });
  }

  for (const paraIndex of PARA_GROUPS.opening) {
    applyParaStyle(doc, paraIndex, {
      alignment: "justify",
      lineSpacing: 160,
      lineSpacingType: "Percent",
      spacingAfter: profile.openingAfter,
    });
    applyCharStyle(doc, paraIndex, {
      fontSize: profile.openingSize,
      bold: false,
    });
  }

  for (const paraIndex of PARA_GROUPS.keyPoint) {
    applyParaStyle(doc, paraIndex, {
      alignment: "justify",
      lineSpacing: 160,
      lineSpacingType: "Percent",
      spacingAfter: profile.keyPointAfter,
    });
    applyCharStyle(doc, paraIndex, {
      fontSize: profile.keyPointSize,
      bold: false,
    });
  }

  for (const paraIndex of PARA_GROUPS.quiz) {
    applyParaStyle(doc, paraIndex, {
      alignment: "justify",
      lineSpacing: 160,
      lineSpacingType: "Percent",
      spacingAfter: profile.quizAfter,
    });
    applyCharStyle(doc, paraIndex, {
      fontSize: profile.quizSize,
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
  const message = error instanceof Error ? error.message : String(error || "worksheet build failed");
  process.stderr.write(`${message}\n`);
  process.exit(1);
});
