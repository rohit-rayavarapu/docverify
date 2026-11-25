import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


SUPPORTED_IMAGES = {".jpg", ".jpeg", ".png"}
MAX_PDF_PAGES = 25


def run_tool(*args: str) -> str:
    result = subprocess.run(
        args,
        capture_output=True,
        timeout=90,
        check=True,
    )
    return result.stdout.decode("utf-8", errors="replace").strip()


def read_image(image_path: Path) -> str:
    return run_tool("tesseract", str(image_path), "stdout", "-l", "eng")


def read_pdf_page(pdf_path: Path, number: int, work_dir: Path) -> dict:
    page = str(number)

    # Read embedded text first. Scanned pages need OCR.
    text = run_tool(
        "pdftotext", "-f", page, "-l", page, str(pdf_path), "-"
    )
    method = "pdf_text"

    if not text:
        prefix = work_dir / f"page-{number}"
        run_tool(
            "pdftoppm",
            "-f", page,
            "-l", page,
            "-scale-to", "2200",
            "-singlefile",
            "-png",
            str(pdf_path),
            str(prefix),
        )
        text = read_image(prefix.with_suffix(".png"))
        method = "ocr"

    return {"page": number, "method": method, "text": text or None}


def extract_document(file_path: Path) -> dict:
    source = file_path.resolve()
    if not source.is_file():
        raise ValueError(f"File not found: {file_path}")

    suffix = source.suffix.lower()

    if suffix in SUPPORTED_IMAGES:
        text = read_image(source)
        pages = [{"page": 1, "method": "ocr", "text": text or None}]

    elif suffix == ".pdf":
        info = run_tool("pdfinfo", str(source))
        match = re.search(r"^Pages:\s+(\d+)\s*$", info, re.MULTILINE)
        if not match:
            raise ValueError("Could not determine the PDF page count.")

        page_count = int(match.group(1))
        if not 1 <= page_count <= MAX_PDF_PAGES:
            raise ValueError(
                f"This demo supports PDFs with 1 to {MAX_PDF_PAGES} pages."
            )

        with tempfile.TemporaryDirectory() as folder:
            pages = [
                read_pdf_page(source, number, Path(folder))
                for number in range(1, page_count + 1)
            ]

    else:
        raise ValueError("Choose a PDF, JPG, JPEG, or PNG file.")

    return {
        "filename": source.name,
        "status": "extracted" if all(page["text"] for page in pages) else "needs_review",
        "pages": pages,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract text from a PDF or image.")
    parser.add_argument("file", type=Path)
    args = parser.parse_args()

    try:
        result = extract_document(args.file)
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode("utf-8", errors="replace").strip()
        print(f"Extraction failed: {detail or error}", file=sys.stderr)
        return 1
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(f"Extraction failed: {error}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())