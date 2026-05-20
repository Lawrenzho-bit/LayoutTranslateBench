"""Tests for the Helsinki-NLP/opus-mt runner (v0.1.6.2).

  - 16-pair model map covers every LTB pair
  - Runner registers as oracle-layout, commercial-safe
  - Prefix-token routing handles the 6 router-model pairs
"""

from __future__ import annotations

from ltbench import LANG_PAIRS
from ltbench.runners.opus_mt_text import _LANG_PAIR_TO_OPUS, OpusMtTextRunner


def test_opus_mt_covers_all_ltb_pairs():
    """Every LTB pair has an opus-mt model + (optional) prefix mapping."""
    missing = [p for p in LANG_PAIRS if p not in _LANG_PAIR_TO_OPUS]
    assert not missing, f"opus-mt model map missing pairs: {missing}"


def test_opus_mt_router_pairs_have_prefix():
    """The 6 multi-target router models require a prefix token."""
    pairs_needing_prefix = {
        "en-zh": ">>cmn_Hans<<",
        "en-zh-tw": ">>cmn_Hant<<",
        "en-ar": ">>ara<<",
        "en-th": ">>tha<<",
        "en-ms": ">>zsm_Latn<<",
        "en-uz": ">>uzb_Latn<<",
        "en-kk": ">>kaz_Cyrl<<",
    }
    for pair, expected_prefix in pairs_needing_prefix.items():
        model_id, prefix = _LANG_PAIR_TO_OPUS[pair]
        assert prefix == expected_prefix, (
            f"{pair}: expected prefix {expected_prefix}, got {prefix}"
        )


def test_opus_mt_single_target_pairs_no_prefix():
    """Single-target opus-mt models don't take a prefix."""
    no_prefix_pairs = {"en-es", "en-de", "en-fr", "en-ja", "en-ru", "en-ko", "en-vi", "en-id", "en-ur"}
    for pair in no_prefix_pairs:
        model_id, prefix = _LANG_PAIR_TO_OPUS[pair]
        assert prefix is None, f"{pair}: expected no prefix, got {prefix}"


def test_opus_mt_runner_manifest():
    """OpusMtTextRunner emits a system manifest with the right metadata."""
    runner = OpusMtTextRunner()
    manifest = runner.system_manifest()
    assert manifest.system_name == "opus-mt-text-oracle"
    assert manifest.system_type == "oracle-layout"
    assert manifest.runner_config.get("commercial_safe") is True
    assert manifest.runner_config.get("covers_16_pairs") is True
    assert "Apache-2.0" in (manifest.notes or "")


def test_opus_mt_uses_only_14_unique_models():
    """The 16 pairs share 14 distinct model IDs.

    Shared models: opus-mt-en-zh (en-zh + en-zh-tw via prefix),
    opus-mt-en-trk (en-uz + en-kk via prefix). Everything else gets its own.
    """
    unique_models = {model_id for model_id, _ in _LANG_PAIR_TO_OPUS.values()}
    assert len(unique_models) == 14, (
        f"expected 14 distinct opus-mt models, got {len(unique_models)}: {unique_models}"
    )


def test_opus_mt_registered_in_runners_init():
    """ltbench.runners exposes get_opus_mt_text_runner."""
    from ltbench import runners
    assert hasattr(runners, "get_opus_mt_text_runner")
