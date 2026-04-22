"""Tests for the deterministic placeholder embedding helper.

Placeholder embedding is a BLAKE2b-chained 384-float unit vector — it carries
zero semantic signal but populates the pgvector column deterministically so
the rest of the persistence layer + IVFFLAT index can be exercised.
"""

from __future__ import annotations

import math

import pytest

from cryptozavr.infrastructure.persistence.embedding import (
    EMBEDDING_DIM,
    placeholder_embedding,
)


class TestPlaceholderEmbedding:
    def test_returns_list_of_384_floats(self) -> None:
        vec = placeholder_embedding("anything")
        assert isinstance(vec, list)
        assert len(vec) == EMBEDDING_DIM == 384
        for f in vec:
            assert isinstance(f, float)

    def test_deterministic_same_input_same_output(self) -> None:
        a = placeholder_embedding('{"name":"x"}')
        b = placeholder_embedding('{"name":"x"}')
        assert a == b

    def test_different_inputs_produce_different_vectors(self) -> None:
        a = placeholder_embedding('{"name":"a"}')
        b = placeholder_embedding('{"name":"b"}')
        c = placeholder_embedding('{"name":"c"}')
        assert a != b
        assert a != c
        assert b != c

    def test_output_is_unit_normalised(self) -> None:
        vec = placeholder_embedding("canonical-spec-json-here")
        norm_sq = sum(f * f for f in vec)
        assert math.isclose(norm_sq, 1.0, rel_tol=1e-6, abs_tol=1e-6)

    def test_empty_string_still_valid_vector(self) -> None:
        vec = placeholder_embedding("")
        assert len(vec) == EMBEDDING_DIM
        # Either all zeros (if BLAKE2b of b"" + index chain happens to decode
        # to pure zero/NaN — extremely unlikely) OR a unit vector.
        norm_sq = sum(f * f for f in vec)
        assert norm_sq == pytest.approx(1.0, rel=1e-6, abs=1e-6) or norm_sq == 0.0
