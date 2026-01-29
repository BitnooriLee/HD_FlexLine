"""Pytest fixtures shared across tests."""
import os

import pytest


@pytest.fixture
def sample_params():
    """Minimal params dict matching what parse_tsp_parameters / generate_hotb_xml expect."""
    return {
        "TCR": 0.00503145,
        "SensorDesign": 5501,
        "CableType": "GreyCable",
        "HeatingPower": 1.5,
        "HeatingTime": 10,
        "SampleTemperature": 21.0,
        "DriftTime": 40,
        "PreMeasurementDelay": 10,
        "MeasurementInterval": 10,
        "NPLC": 1,
        "PowerLineFrequency": 50,
        "SoftwareVersion": "7.8 Beta 7",
        "AvailableProbingDepth": 20,
        "InsulationType": "Kapton",
        "HolderType": "CableDirectlyConnectedToSensor",
        "AnalysisType": "Standard",
        "MinIntervalSize": 20,
        "FullIntervalSize": 60,
        "SelectionStartIndex": 10,
        "SelectionEndIndex": 200,
        "SpecHeatCapOfSensor": 0.0063995923422626,
        "SpecificHeatOfSample": 1e-06,
        "SpecHeatCapSensorCal": True,
        "UseDefaultSpecHeatCapSensor": True,
        "TimeCorrection": True,
        "CalculationID": 1,
        "THERMAL_EQUILIBRIUM_TIME": 600,
        "measurement_points": 201,
        "TRIGGER_OVERHEAD": 0.021,
    }


@pytest.fixture
def sample_buffer_lines():
    """Example buffer lines: timestamp, voltage, current per line."""
    return [
        "0.0,0.01,0.001",
        "0.1,0.01,0.001",
        "0.2,0.01,0.001",
    ]


@pytest.fixture
def sample_measurement_data(sample_buffer_lines):
    """One iteration's measurement buffers as returned by call_tsp_function."""
    return {
        "R0_defbuffer1": ["0.0,0.01,0.001", "0.1,0.01,0.001"],
        "Drift_defbuffer2": sample_buffer_lines,
        "Transient_defbuffer1": sample_buffer_lines,
    }
