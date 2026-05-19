"""Tests for v0.1.1 methodology fixes:
  - Language-detection penalty in chrF
  - Coverage-aware Kendall tau
  - Bootstrap CIs for LTB-100
"""

from __future__ import annotations

import pytest

from ltbench.metrics.bootstrap import bootstrap_ci
from ltbench.metrics.language import chrf_with_lang_check, is_target_language
from ltbench.metrics.reading_order import coverage_aware_tau, normalized_kendall_tau


# ---------- Language-detection penalty ----------


def test_language_check_passes_target_spanish():
    assert is_target_language("Certificado de Nacimiento", "en-es") is True


def test_language_check_fails_english_for_spanish():
    # English text submitted for a Spanish target → fail
    assert is_target_language("Certificate of Birth in long form", "en-es") is False


def test_language_check_short_string_passes():
    # Short/numeric strings pass — too little signal to penalise
    assert is_target_language("$4.50", "en-es") is True
    assert is_target_language("2018", "en-es") is True


def test_language_check_chinese_target():
    assert is_target_language("出生证明", "en-zh") is True
    assert is_target_language("This is English text", "en-zh") is False


def test_language_check_arabic_target():
    assert is_target_language("شهادة ميلاد", "en-ar") is True


def test_language_check_malay_accepts_indonesian():
    # Malay and Indonesian are mutually intelligible — langdetect often
    # returns "id" for short Malay strings. Both should pass.
    assert is_target_language("Sijil Kelahiran adalah dokumen rasmi", "en-ms") is True


def test_chrf_with_lang_check_zeros_wrong_language():
    # English hypothesis, Spanish target: chrF must be 0 despite character overlap
    score = chrf_with_lang_check(
        "Certificate of Birth is the official document",
        "Certificado de Nacimiento es el documento oficial",
        "en-es",
    )
    assert score == 0.0


def test_chrf_with_lang_check_passes_target_language():
    # Spanish hypothesis for Spanish target: scores normally
    score = chrf_with_lang_check(
        "Certificado de Nacimiento",
        "Certificado de Nacimiento",
        "en-es",
    )
    assert score == 100.0


# ---------- Coverage-aware Kendall tau ----------


def test_coverage_aware_tau_full_coverage():
    # All 7 GT regions matched, in order → tau = 1.0, coverage = 1.0
    src = [0, 1, 2, 3, 4, 5, 6]
    pred = [0, 1, 2, 3, 4, 5, 6]
    assert coverage_aware_tau(src, pred, n_gt_regions=7) == 1.0


def test_coverage_aware_tau_partial_coverage():
    # Only 1 region matched out of 7 → base tau is 1.0 (singleton), but
    # coverage = 1/7 → coverage-aware tau ≈ 0.143. This is the bug v0.1.1 fixes.
    src = [0]
    pred = [0]
    score = coverage_aware_tau(src, pred, n_gt_regions=7)
    assert abs(score - 1 / 7) < 1e-9


def test_coverage_aware_tau_zero_matched():
    # No regions matched → tau = 0
    score = coverage_aware_tau([], [], n_gt_regions=7)
    assert score == 0.0


def test_coverage_aware_tau_half_coverage_perfect_order():
    # Match 4 of 8 in perfect order
    src = [0, 1, 2, 3]
    pred = [0, 1, 2, 3]
    score = coverage_aware_tau(src, pred, n_gt_regions=8)
    assert abs(score - 0.5) < 1e-9


def test_normalized_kendall_tau_singleton_unchanged():
    # Base normalized_kendall_tau still returns 1.0 for singleton; the change
    # is at the composite level via coverage_aware_tau.
    assert normalized_kendall_tau([5], [5]) == 1.0


# ---------- Bootstrap CIs ----------


def test_bootstrap_ci_single_value():
    # On singleton: point = low = high
    point, low, high = bootstrap_ci([50.0])
    assert point == low == high == 50.0


def test_bootstrap_ci_constant_values():
    # No variance → CI collapses to the constant
    point, low, high = bootstrap_ci([42.0, 42.0, 42.0, 42.0, 42.0])
    assert point == 42.0
    assert low == 42.0
    assert high == 42.0


def test_bootstrap_ci_brackets_mean():
    # CI should bracket the mean for a varied sample
    point, low, high = bootstrap_ci([10.0, 20.0, 30.0, 40.0, 50.0])
    assert low <= point <= high
    assert low < point < high  # non-degenerate CI


def test_bootstrap_ci_reproducibility():
    # Same seed → same CI
    a = bootstrap_ci([1.0, 2.0, 3.0, 4.0, 5.0])
    b = bootstrap_ci([1.0, 2.0, 3.0, 4.0, 5.0])
    assert a == b


def test_bootstrap_ci_widens_with_variance():
    # Higher variance → wider CI
    _, low_narrow, high_narrow = bootstrap_ci([50.0, 51.0, 49.0, 50.0, 50.0])
    _, low_wide, high_wide = bootstrap_ci([10.0, 90.0, 30.0, 80.0, 50.0])
    width_narrow = high_narrow - low_narrow
    width_wide = high_wide - low_wide
    assert width_wide > width_narrow


def test_bootstrap_ci_empty():
    point, low, high = bootstrap_ci([])
    assert point == low == high == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
