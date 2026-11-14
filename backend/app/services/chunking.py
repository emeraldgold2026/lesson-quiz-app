from app.clients.protocols import ChunkRecord

TOKENS_PER_WORD = 1.3


def chunk_pages(pages: list[tuple[int, str]], max_tokens: int = 650,
                overlap_tokens: int = 60) -> list[ChunkRecord]:
    """Split pages into paragraph-aware chunks of at most ``max_tokens`` tokens.

    Tokens are estimated as whitespace words * 1.3. ``overlap_tokens`` is the
    number of trailing words of the previous chunk repeated at the start of the
    next one; overlap words count toward the size limit.
    """
    max_words = int(max_tokens / TOKENS_PER_WORD)
    overlap_words = overlap_tokens
    if overlap_words >= max_words:
        raise ValueError("overlap_tokens must be smaller than the chunk size in words")
    # Oversized paragraphs are split so each piece still fits alongside the overlap.
    piece_words = max_words - overlap_words

    # flatten to (page_order, paragraph_words), splitting oversized paragraphs
    units: list[tuple[int, list[str]]] = []
    for page_order, text in pages:
        for para in (p.strip() for p in text.split("\n\n")):
            if not para:
                continue
            ws = para.split()
            for i in range(0, len(ws), piece_words):
                units.append((page_order, ws[i:i + piece_words]))

    chunks: list[ChunkRecord] = []
    cur: list[str] = []
    cur_page = 0
    carry: list[str] = []

    def flush():
        nonlocal cur, carry
        if not cur:
            return
        chunks.append(ChunkRecord(cur_page, len(chunks), " ".join(carry + cur)))
        carry = cur[-overlap_words:] if overlap_words else []
        cur = []

    for page_order, ws in units:
        if cur and len(carry) + len(cur) + len(ws) > max_words:
            flush()
        if not cur:
            cur_page = page_order
        cur.extend(ws)
    flush()
    return chunks
