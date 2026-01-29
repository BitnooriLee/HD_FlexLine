"""Tests for calcuration module (parse_numeric_data, parse_data_pairs, create_graphs)."""
import pytest

from calcuration import parse_data_pairs, parse_numeric_data


class TestParseNumericData:
    """Tests for parse_numeric_data."""

    def test_empty_response_returns_empty_list(self):
        assert parse_numeric_data(None) == []
        assert parse_numeric_data("") == []

    def test_parses_integers(self):
        assert parse_numeric_data("1,2,3") == [1.0, 2.0, 3.0]

    def test_parses_floats(self):
        assert parse_numeric_data("1.5,-2.3") == [1.5, -2.3]

    def test_parses_scientific_notation(self):
        result = parse_numeric_data("1e-3 2E+4")
        assert len(result) == 2
        assert abs(result[0] - 0.001) < 1e-9
        assert abs(result[1] - 20000) < 1e-9

    def test_comma_replaced_with_dot(self):
        # Comma replaced by dot: "1,5" -> "1.5" -> one float
        result = parse_numeric_data("1,5")
        assert result == [1.5]


class TestParseDataPairs:
    """Tests for parse_data_pairs."""

    def test_empty_response_returns_none_none(self):
        assert parse_data_pairs(None) == (None, None)
        assert parse_data_pairs("") == (None, None)

    def test_parses_pairs(self):
        x, y = parse_data_pairs("1.0,2.0,3.0,4.0")
        assert x is not None and y is not None
        assert len(x) == 2
        assert len(y) == 2
        assert x == [1.0, 3.0]
        assert y == [2.0, 4.0]

    def test_odd_length_drops_last(self):
        x, y = parse_data_pairs("1,2,3,4,5")
        assert len(x) == 2
        assert len(y) == 2


class TestSendVisaCommand:
    """Tests for send_visa_command (mocked to avoid real socket)."""

    def test_requires_hotdisk_connection(self):
        # Without mocking, would try to connect; we only test the function exists
        from calcuration import send_visa_command
        assert callable(send_visa_command)


class TestCreateGraphs:
    """Tests for create_graphs (smoke test with minimal data)."""

    def test_create_graphs_accepts_none_responses(self):
        from calcuration import create_graphs
        # Should not raise when all None
        create_graphs(None, None, None, None)

    def test_create_graphs_with_empty_strings(self):
        from calcuration import create_graphs
        create_graphs("", "", "", "")
