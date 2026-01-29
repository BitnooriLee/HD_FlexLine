"""Tests for tps_measurement module (parse_tsp_parameters, generate_hotb_xml, generate_signal_xml)."""
import os

import pytest

from tps_measurement import (
    generate_hotb_xml,
    generate_signal_xml,
    parse_tsp_parameters,
)


class TestParseTspParameters:
    """Tests for parse_tsp_parameters."""

    def test_missing_file_returns_defaults(self):
        params = parse_tsp_parameters("nonexistent_file_xyz.tsp")
        assert isinstance(params, dict)
        assert params["HeatingPower"] == 1.5
        assert params["HeatingTime"] == 10
        assert params["NPLC"] == 1
        assert params["measurement_points"] == 201
        assert params["TRIGGER_OVERHEAD"] == 0.021

    def test_existing_tsp_file_returns_params(self):
        # flexline_script.tsp exists and has TRIGGER_OVERHEAD = 0.021 (no 'local')
        if not os.path.exists("flexline_script.tsp"):
            pytest.skip("flexline_script.tsp not found")
        params = parse_tsp_parameters("flexline_script.tsp")
        assert isinstance(params, dict)
        assert "HeatingPower" in params
        assert "measurement_points" in params
        assert params.get("TRIGGER_OVERHEAD") == 0.021

    def test_parsed_params_have_expected_types(self):
        params = parse_tsp_parameters("nonexistent_xyz.tsp")
        assert isinstance(params["HeatingPower"], (int, float))
        assert isinstance(params["SampleTemperature"], (int, float))
        assert isinstance(params["SensorDesign"], (int, float))
        assert isinstance(params["CableType"], str)
        assert isinstance(params["SpecHeatCapSensorCal"], bool)


class TestGenerateSignalXml:
    """Tests for generate_signal_xml."""

    def test_generates_drift_signal(self):
        timestamps = [0.0, 0.1, 0.2]
        voltages = [0.01, 0.01, 0.01]
        currents = [0.001, 0.001, 0.001]
        xml = generate_signal_xml("Drift", timestamps, voltages, currents)
        assert "<Signal type=" in xml
        assert "Drift" in xml
        assert "<timestamps>" in xml
        assert "<voltages>" in xml
        assert "<currents>" in xml
        assert "0.0" in xml or "0" in xml
        assert "</Signal>" in xml

    def test_generates_transient_signal(self):
        xml = generate_signal_xml("Transient", [1.0], [2.0], [3.0])
        assert "Transient" in xml
        assert "VoltCurrentSignal" in xml

    def test_empty_arrays_allowed(self):
        xml = generate_signal_xml("Drift", [], [], [])
        assert "Drift" in xml
        assert "<timestamps>" in xml


class TestGenerateHotbXml:
    """Tests for generate_hotb_xml."""

    def test_generates_valid_xml_structure(self, sample_params, sample_measurement_data):
        all_measurements = [sample_measurement_data]
        xml = generate_hotb_xml(sample_params, all_measurements, 1)
        assert xml.strip().startswith("<?xml")
        assert "<ExperimentBatch" in xml
        assert "<Schedule>" in xml
        assert "<ResultSteps>" in xml
        assert "</ExperimentBatch>" in xml

    def test_includes_params_in_schedule(self, sample_params, sample_measurement_data):
        xml = generate_hotb_xml(sample_params, [sample_measurement_data], 1)
        assert str(sample_params["HeatingPower"]) in xml
        assert str(sample_params["HeatingTime"]) in xml
        assert sample_params["CableType"] in xml
        assert sample_params["SoftwareVersion"] in xml

    def test_multiple_iterations_produce_multiple_result_steps(
        self, sample_params, sample_measurement_data
    ):
        all_measurements = [sample_measurement_data, sample_measurement_data]
        xml = generate_hotb_xml(sample_params, all_measurements, 2)
        assert "<ExecutedStep" in xml
        # Should have two ExecutedStep blocks
        assert xml.count("<ExecutedStep type=") >= 2
