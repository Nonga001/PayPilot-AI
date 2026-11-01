import hashlib
import logging
import time

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core import audit, config, db

from . import reader

log = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/read-invoice")
async def read_invoice(file: UploadFile = File(...)):
    """Read a supplier invoice and draft a payment request. Never pays anything by itself."""
    t0 = time.perf_counter()
    data = await file.read(reader.MAX_PDF_BYTES + 1)
    if not data:
        raise HTTPException(400, "The file is empty.")
    try:
        kind = reader.sniff(data)
        limit = reader.MAX_PDF_BYTES if kind == "pdf" else reader.MAX_IMAGE_BYTES
        if len(data) > limit:
            raise reader.DocumentError(f"Files up to {limit // (1024 * 1024)} MB, please.")

        pages = 1
        if kind == "pdf":
            text, pages = reader.pdf_text(data)
            if config.GROQ_API_KEY:
                try:
                    raw, method = await reader.groq_fields(text), "ai"
                except Exception as e:  # network, rate limit, bad JSON: the rules still read the PDF
                    log.warning("Groq invoice read failed, using rules: %s", type(e).__name__)
                    raw, method = reader.rules_fields(text), "rules"
            else:
                raw, method = reader.rules_fields(text), "rules"
        else:
            if not config.GROQ_API_KEY:
                raise reader.DocumentError("Reading photos needs the AI (GROQ_API_KEY). Upload the invoice as a PDF instead.")
            try:
                raw, text = await reader.vision_fields(data, kind)
                method = "vision"
            except Exception as e:
                log.warning("Groq vision read failed: %s", type(e).__name__)
                raise reader.DocumentError("Couldn't read this photo right now. Try a PDF, or type the request.") from e
    except reader.DocumentError as e:
        raise HTTPException(422, str(e)) from e

    fields, warnings, injection = reader.check(raw, text)
    if kind != "pdf":
        warnings.insert(0, "Read from a photo. Check the amount against the invoice before you send it.")
    digest = hashlib.sha256(data).hexdigest()
    blocked = injection is not None
    with db.write() as c:
        audit.append(c, "document.rejected" if blocked else "document.read", None, {
            "file_sha256": digest, "type": kind, "pages": pages, "method": method,
            **({"injection": injection} if blocked else
               {"amount": fields["amount"], "currency": fields["currency"], "invoice_number": fields["invoice_number"]}),
        })
    return {
        "type": kind,
        "pages": pages,
        "method": method,
        "model": config.VISION_MODEL if method == "vision" else (config.GROQ_MODEL if method == "ai" else "rules"),
        "ms": int((time.perf_counter() - t0) * 1000),
        "fields": fields,
        "warnings": warnings,
        "blocked": blocked,
        "injection": injection,
        "request": None if blocked else reader.request_sentence(fields),
        "sha256": digest,
    }
