import pytest

from edit_detector.caption import LlamaCaptioner, clean_caption
from edit_detector.errors import AppError


def test_cleanup_preserves_one_sentence():
    assert clean_caption('Caption: A red cup sits on a table. There is a spoon.') == "A red cup sits on a table."
    assert clean_caption('1. The image shows a cat beside a window') == "A cat beside a window"


@pytest.mark.parametrize("raw", ["", "Yes.", "I cannot describe this image.", "cat cat cat cat", "<|assistant|> A cat sits in the room."])
def test_malformed_captions_are_rejected(raw):
    with pytest.raises(ValueError):
        clean_caption(raw)


def tiny_model(tmp_path):
    p = tmp_path / "model.gguf"
    p.write_bytes(b"GGUFtest")
    return p


def test_retries_only_once(monkeypatch, tmp_path):
    path = tiny_model(tmp_path)
    model = LlamaCaptioner(model=path, mmproj=path, binary="fake")
    calls = []
    def fake(args, **kwargs):
        calls.append(args)
        return "bad"
    monkeypatch.setattr("edit_detector.caption.run_process", fake)
    with pytest.raises(AppError, match="two attempts"):
        model.caption(path)
    assert len(calls) == 2
    assert all("--offline" in args and "--no-mmproj-offload" in args for args in calls)


def test_retry_can_recover(monkeypatch, tmp_path):
    path = tiny_model(tmp_path)
    model = LlamaCaptioner(model=path, mmproj=path, binary="fake")
    responses = iter(["", "A cat sits beside a window."])
    monkeypatch.setattr("edit_detector.caption.run_process", lambda *a, **k: next(responses))
    assert model.caption(path).attempts == 2


def test_missing_projector_pair(tmp_path):
    with pytest.raises(AppError, match="both"):
        LlamaCaptioner(model=tmp_path / "model.gguf")


def test_short_phrases():
    assert clean_caption("Red cup") == "Red cup"
    assert clean_caption("Caption: cat face") == "Cat face"
