import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE | re.DOTALL)
ALT_ATTR_RE = re.compile(r"\balt\s*=", re.IGNORECASE)
OUTLINE_NONE_RE = re.compile(r"<(input|textarea|select|button)\b[^>]*\boutline-none\b[^>]*>", re.IGNORECASE | re.DOTALL)
FOCUS_TOKEN_RE = re.compile(r"\bfocus:[^\s\"']+|\bfocus:ring-[^\s\"']+|\bfocus-within:[^\s\"']+", re.IGNORECASE)
GRAY_LOW_CONTRAST_RE = re.compile(r"\btext-gray-(300|400)\b")


class Command(BaseCommand):
    help = "A11y checks: missing alt (critical), outline-none without focus style (warning), low-contrast gray text report."

    def handle(self, *args, **options):
        base_dir = Path(settings.BASE_DIR)
        template_files = sorted(base_dir.glob("**/templates/**/*.html"))

        missing_alt = []
        missing_focus = []
        low_contrast = []

        for path in template_files:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = path.read_text(encoding="utf-8-sig")

            rel = path.relative_to(base_dir).as_posix()
            lines = text.splitlines()

            for i, line in enumerate(lines, start=1):
                if "text-gray-300" in line or "text-gray-400" in line:
                    matches = GRAY_LOW_CONTRAST_RE.findall(line)
                    if matches:
                        low_contrast.append((rel, i, line.strip()))

            for tag in IMG_TAG_RE.finditer(text):
                tag_text = tag.group(0)
                if ALT_ATTR_RE.search(tag_text):
                    continue
                line_no = text.count("\n", 0, tag.start()) + 1
                missing_alt.append((rel, line_no, tag_text.strip()))

            for tag in OUTLINE_NONE_RE.finditer(text):
                tag_text = tag.group(0)
                if FOCUS_TOKEN_RE.search(tag_text):
                    continue
                line_no = text.count("\n", 0, tag.start()) + 1
                missing_focus.append((rel, line_no, tag_text.strip()))

        self.stdout.write(self.style.NOTICE(f"[SCAN] template files: {len(template_files)}"))

        if missing_focus:
            self.stdout.write(self.style.WARNING(f"[WARN] outline-none without focus style: {len(missing_focus)}"))
            for rel, line_no, _ in missing_focus[:50]:
                self.stdout.write(f"  - {rel}:{line_no}")

        if low_contrast:
            self.stdout.write(f"[INFO] text-gray-300/400 occurrences: {len(low_contrast)}")
            for rel, line_no, line_text in low_contrast[:50]:
                self.stdout.write(f"  - {rel}:{line_no} | {line_text}")

        if missing_alt:
            self.stdout.write(self.style.ERROR(f"[CRITICAL] missing img alt: {len(missing_alt)}"))
            for rel, line_no, _ in missing_alt[:50]:
                self.stdout.write(f"  - {rel}:{line_no}")
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS("[OK] 0 critical issues (missing alt)."))
