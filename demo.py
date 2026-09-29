"""
Document processing agent — CLI demo.

Usage:
    python generate_sample.py                     # creates test documents once
    python demo.py sample_documents/invoice_clean.png
    python demo.py sample_documents/*.png          # process several at once
"""

import sys
import json
import glob

from extractor import process_document


def print_report(file_path: str, result: dict):
    extracted = result["extracted"]
    flags = result["flags"]

    print("\n" + "=" * 60)
    print(f"Document: {file_path}")
    print("=" * 60)
    print(json.dumps(extracted, indent=2))

    if flags:
        print("\n⚠  FLAGS FOR REVIEW:")
        for flag in flags:
            print(f"  - {flag}")
    else:
        print("\n✓ No issues detected.")


def main():
    if len(sys.argv) < 2:
        print("Usage: python demo.py <path-to-image-or-images>")
        print("Example: python demo.py sample_documents/invoice_clean.png")
        sys.exit(1)

    # Expand any glob patterns the shell didn't already expand
    file_paths = []
    for arg in sys.argv[1:]:
        matches = glob.glob(arg)
        file_paths.extend(matches if matches else [arg])

    for file_path in file_paths:
        try:
            result = process_document(file_path)
            print_report(file_path, result)
        except Exception as e:
            print(f"\nFailed to process {file_path}: {e}")


if __name__ == "__main__":
    main()
