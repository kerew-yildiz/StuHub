"""FIB normalizasyon/eşleştirme testleri (Yetenek 04 §4)."""

from src.services.fib_utils import fib_is_correct, normalize_fib


def test_normalize_turkish():
    assert normalize_fib("  Hücre Zarı. ") == "hücre zarı"
    assert normalize_fib("İŞARETÇİLER!") == "işaretçiler"
    assert normalize_fib("çift  yönlü\nliste") == "çift yönlü liste"
    # i/ı ayrımı korunur
    assert normalize_fib("kilit") != normalize_fib("kılıt")


def test_fib_matching():
    assert fib_is_correct("Hücre zarı", ["hücre zarı", "plazma zarı"])
    assert fib_is_correct("HÜCRE ZARI!", ["hücre zarı"])
    assert fib_is_correct("çift yönlü", ["çift yönlü", "çift yönlü bağlı liste"])
    assert not fib_is_correct("", ["cevap"])
    assert not fib_is_correct("yanlış cevap", ["doğru cevap"])
