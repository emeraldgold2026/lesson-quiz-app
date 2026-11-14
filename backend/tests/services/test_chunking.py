from app.services.chunking import chunk_pages


def words(n, tag="w"):
    return " ".join(f"{tag}{i}" for i in range(n))


def test_short_text_single_chunk():
    chunks = chunk_pages([(0, "one para\n\nsecond para")])
    assert len(chunks) == 1 and chunks[0].chunk_index == 0 and chunks[0].page_order == 0


def test_splits_on_paragraph_boundaries_and_indexes_sequentially():
    pages = [(0, words(300, "a") + "\n\n" + words(300, "b")), (1, words(300, "c"))]
    chunks = chunk_pages(pages, max_tokens=500, overlap_tokens=20)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert len(chunks) >= 2
    assert chunks[-1].page_order == 1


def test_overlap_repeats_tail_of_previous_chunk():
    chunks = chunk_pages([(0, words(300, "a") + "\n\n" + words(300, "b"))], max_tokens=500, overlap_tokens=20)
    tail = chunks[0].text.split()[-20:]
    assert chunks[1].text.split()[:20] == tail


def test_oversized_paragraph_is_split_by_words():
    chunks = chunk_pages([(0, words(2000))], max_tokens=500, overlap_tokens=0)
    assert len(chunks) > 1
    assert all(len(c.text.split()) * 1.3 <= 500 + 1 for c in chunks)


def test_chunks_with_overlap_never_exceed_limit():
    chunks = chunk_pages([(0, words(2000))], max_tokens=500, overlap_tokens=20)
    assert len(chunks) > 1
    assert all(len(c.text.split()) * 1.3 <= 500 for c in chunks)
