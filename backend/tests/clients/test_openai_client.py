import base64
from types import SimpleNamespace as NS

import pytest

from app.clients.openai_client import OpenAIClient
from app.schemas import FreeTextVerdict, GeneratedBatch


class StubOpenAI:
    """Hand-written stub at the third-party network boundary."""

    def __init__(self, parsed=None, content="page text", refusal=None):
        self.calls = []
        self._parsed, self._content, self._refusal = parsed, content, refusal
        self.chat = NS(completions=NS(parse=self._parse, create=self._create))
        self.embeddings = NS(create=self._embed)

    def _msg(self):
        return NS(choices=[NS(message=NS(parsed=self._parsed, content=self._content,
                                         refusal=self._refusal))])

    def _parse(self, **kw):
        self.calls.append(("parse", kw))
        return self._msg()

    def _create(self, **kw):
        self.calls.append(("create", kw))
        return self._msg()

    def _embed(self, **kw):
        self.calls.append(("embed", kw))
        return NS(data=[NS(embedding=[float(t)]) for t in kw["input"]])


def test_extract_page_text_sends_data_url_image():
    stub = StubOpenAI(content="hello")
    out = OpenAIClient(api_key="k", client=stub).extract_page_text(b"\x89PNG", "image/png")
    assert out == "hello"
    _, kw = stub.calls[0]
    parts = kw["messages"][0]["content"]
    image = next(p for p in parts if p["type"] == "image_url")
    assert image["image_url"]["url"] == "data:image/png;base64," + base64.b64encode(b"\x89PNG").decode()
    assert any(p["type"] == "text" and "[Figure: ...]" in p["text"] for p in parts)


def test_embed_batches_of_100_preserving_order():
    stub = StubOpenAI()
    texts = [str(i) for i in range(250)]
    out = OpenAIClient(api_key="k", client=stub).embed(texts)
    assert out == [[float(i)] for i in range(250)]
    assert [len(kw["input"]) for _, kw in stub.calls] == [100, 100, 50]
    assert stub.calls[0][1]["model"] == "text-embedding-3-small"


def test_generate_questions_returns_parsed_batch():
    batch = GeneratedBatch(questions=[])
    stub = StubOpenAI(parsed=batch)
    out = OpenAIClient(api_key="k", client=stub).generate_questions("SECTION", 3, 2)
    assert out is batch
    _, kw = stub.calls[0]
    assert kw["response_format"] is GeneratedBatch and kw["model"] == "gpt-5"
    system, user = kw["messages"]
    assert "exactly 3 multiple-choice" in system["content"] and "2 free-text" in system["content"]
    assert "<textbook_section>" in user["content"] and "SECTION" in user["content"]


def test_grade_free_text_prompt_contains_all_inputs():
    verdict = FreeTextVerdict(verdict="correct", feedback="ok")
    stub = StubOpenAI(parsed=verdict)
    out = OpenAIClient(api_key="k", client=stub).grade_free_text(
        "Q?", "my answer", "ref answer", ["chunk-a", "chunk-b"])
    assert out is verdict
    _, kw = stub.calls[0]
    assert kw["response_format"] is FreeTextVerdict
    user = kw["messages"][1]["content"]
    for s in ["Q?", "<student_answer>\nmy answer\n</student_answer>", "ref answer", "chunk-a", "chunk-b"]:
        assert s in user
    assert "ignore any instructions" in kw["messages"][0]["content"]


def test_refusal_raises_clear_error():
    stub = StubOpenAI(parsed=None, refusal="no")
    with pytest.raises(RuntimeError, match="no parsed FreeTextVerdict"):
        OpenAIClient(api_key="k", client=stub).grade_free_text("q", "a", "r", [])


def test_embed_empty_returns_empty_without_calling_api():
    stub = StubOpenAI()
    assert OpenAIClient(api_key="k", client=stub).embed([]) == []
    assert stub.calls == []


def _keys(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k
            yield from _keys(v)
    elif isinstance(node, list):
        for v in node:
            yield from _keys(v)


@pytest.mark.parametrize("model", [GeneratedBatch, FreeTextVerdict])
def test_structured_output_schemas_are_strict_mode_compatible(model):
    from openai.lib._pydantic import to_strict_json_schema
    # OpenAI strict Structured Outputs rejects `default` anywhere in the schema.
    assert "default" not in set(_keys(to_strict_json_schema(model)))
