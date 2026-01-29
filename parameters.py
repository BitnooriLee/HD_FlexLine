experiment_parameters = {
    # Measurement Parameters
    'HeatingPower': 1.5,           # Number (float) - Default: 1.5 (Watts)
    'HeatingTime': 10,             # Number (float) - Default: 10 (seconds)
    'NPLC': 1,                     # Number (float) - Default: 1 (Power Line Cycles)
    'DriftTime': 40,              # Number (int) - Default: 40 (seconds)
    'measurement_points': 201,     # Number (int) - Default: 201 (data points)
    'TRIGGER_OVERHEAD': 0.021,     # Number (float) - Default: 0.021 (seconds)
    
    # Thermal Parameters
    'TCR': 0.00503145,            # Number (float) - Default: 0.00503145 (K⁻¹)
    'SampleTemperature': 21.0,     # Number (float) - Default: 21.0 (°C)
    'THERMAL_EQUILIBRIUM_TIME': 600,  # Number (int) - Default: 600 (seconds = 10 min)
    
    # Sensor Configuration
    'SensorDesign': 5501,          # Number (int) - Default: 5501
    'CableType': 'GreyCable',      # String - Default: 'GreyCable'
    'InsulationType': 'Kapton',    # String - Default: 'Kapton'
    'HolderType': 'CableDirectlyConnectedToSensor',  # String - Default: 'CableDirectlyConnectedToSensor'
    'AvailableProbingDepth': 20,   # Number (int) - Default: 20 (mm)
    
    # Schedule Parameters
    'PreMeasurementDelay': 10,    # Number (int) - Default: 10 (seconds)
    'MeasurementInterval': 10,    # Number (int) - Default: 10 (seconds)
    
    # Analysis Parameters
    'AnalysisType': 'Standard',    # String - Default: 'Standard'
    'MinIntervalSize': 20,         # Number (int) - Default: 20
    'FullIntervalSize': 60,        # Number (int) - Default: 60
    'SelectionStartIndex': 10,      # Number (int) - Default: 10
    'SelectionEndIndex': 200,      # Number (int) - Default: 200
    
    # Calculation Parameters
    'SpecHeatCapOfSensor': 0.0063995923422626,  # Number (float) - Default: 0.0063995923422626
    'SpecificHeatOfSample': 1E-06,  # Number (float/scientific) - Default: 1E-06
    'SpecHeatCapSensorCal': True,  # Boolean - Default: True
    'UseDefaultSpecHeatCapSensor': True,  # Boolean - Default: True
    'TimeCorrection': True,        # Boolean - Default: True
    'CalculationID': 1,            # Number (int) - Default: 1
    
    # System Parameters
    'PowerLineFrequency': 50,      # Number (int) - Default: 50 (Hz)
    'SoftwareVersion': '8.0 Beta 4',
    # Runner Settings
    'NUM_ITERATIONS': 1,          # Number (int) - 
}
