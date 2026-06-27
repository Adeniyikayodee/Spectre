"""Read the litigation bundle from the witness statement folder, read only.

Each .docx becomes a list of citable passages: (paragraph index, text). We only
ever open files for reading; the folder is never modified, moved, or renamed. A
citable passage is one non-empty Word paragraph, identified by (document, paragraph).
"""
import os
from pathlib import Path

# The folder already in the codebase. Overridable by env, but never written to.
_DEFAULT_DIR = Path(__file__).resolve().parent.parent / "WITHNESSSTATEMENS"

# Filenames that are pleadings (the source of pleaded propositions); the rest is evidence.
_PLEADING_MARKERS = ("Claim_Form", "Particulars_of_Claim")


def bundle_dir() -> Path:
    return Path(os.getenv("BUNDLE_DIR", str(_DEFAULT_DIR)))


def read_bundle(folder: str | None = None) -> list[dict]:
    """List the .docx documents and index each into non-empty paragraphs.
    Returns [{name, kind: pleading|evidence, passages: [{para, text}]}]."""
    from docx import Document  # lazy import of python-docx

    root = Path(folder or bundle_dir())
    docs = []
    for path in sorted(root.glob("*.docx")):
        if path.name.startswith("~$"):  # skip Word lock files
            continue
        document = Document(str(path))  # opened read only; we never call .save()
        passages = [
            {"para": i, "text": p.text.strip()}
            for i, p in enumerate(document.paragraphs)
            if p.text.strip()
        ]
        kind = "pleading" if any(m in path.name for m in _PLEADING_MARKERS) else "evidence"
        docs.append({"name": path.name, "kind": kind, "passages": passages})
    return docs


def pleadings_text(docs: list[dict]) -> str:
    """The pleadings as plain text, for the extraction agent to read."""
    out = []
    for d in docs:
        if d["kind"] == "pleading":
            out.append(f"=== {d['name']} ===")
            out.extend(p["text"] for p in d["passages"])
    return "\n".join(out)


def evidence_passages(docs: list[dict], max_chars: int = 240) -> list[dict]:
    """A flat list of evidence passages with their exact source, for mapping.
    Each item is {doc, para, text}; text is trimmed to keep prompts cheap."""
    items = []
    for d in docs:
        if d["kind"] == "evidence":
            for p in d["passages"]:
                items.append({"doc": d["name"], "para": p["para"], "text": p["text"][:max_chars]})
    return items


def get_passage(docs: list[dict], doc_name: str, para: int) -> str | None:
    """The full verbatim text of one passage, for citing the exact source."""
    for d in docs:
        if d["name"] == doc_name:
            for p in d["passages"]:
                if p["para"] == para:
                    return p["text"]
    return None
