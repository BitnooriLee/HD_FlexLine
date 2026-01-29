#!/usr/bin/env python3
import pyvisa
import time
import os
from datetime import datetime
import re
from dotenv import load_dotenv
from parameters import experiment_parameters
load_dotenv()

def connect_to_instrument(instrument_ip="192.168.169.97"):
    """Connect to the Keithley instrument"""
    print("Connecting to instrument...")
    print(f"Instrument IP: {instrument_ip}")
    
    try:
        rm = pyvisa.ResourceManager()
        instr = rm.open_resource(f"TCPIP0::{instrument_ip}::INSTR")
        
        # Set communication parameters
        instr.timeout = 30000  # 30 second default timeout
        instr.read_termination = '\n'
        instr.write_termination = '\n'
        instr.chunk_size = 20480  # Increase chunk size for large data transfers
        
        # Clear any pending data
        try:
            instr.clear()
        except:
            pass
        
        # Test connection
        idn = instr.query("*IDN?")
        print(f"✓ Connected: {idn.strip()}")
        
        return instr
        
    except Exception as e:
        print(f"✗ Failed to connect: {e}")
        return None

def load_tsp_script(instr, script_name="myworkers", tsp_file="test_728_simplified_test.tsp"):
    """Load TSP script onto the instrument with improved timeout handling"""
    print(f"Loading TSP script: {tsp_file}")
    
    try:
        # Check if TSP file exists
        if not os.path.exists(tsp_file):
            print(f"✗ TSP file not found: {tsp_file}")
            return False
        
        # Clear existing scripts
        print("Clearing existing scripts...")
        try:
            instr.write(f"script.delete('{script_name}')")
            time.sleep(2)
        except:
            pass
        
        # Start script loading
        print("Loading script line by line...")
        instr.write(f"loadscript {script_name}")
        time.sleep(1)
        
        with open(tsp_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.rstrip()
                if line and not line.startswith('--'):  # Skip empty lines and comments
                    try:
                        # Add small delay for complex lines
                        if len(line) > 100 or 'string.format' in line or '<' in line:
                            time.sleep(0.1)
                        
                        instr.write(line)
                        
                        # Add delay after every 50 lines to prevent timeout
                        if line_num % 50 == 0:
                            time.sleep(0.5)
                            #print(f"Loaded {line_num} lines...")
                            
                    except Exception as e:
                        print(f"Error at line {line_num}: {e}")
                        # Try to clean up the line
                        clean_line = line.replace('°', 'deg').replace('±', '+/-')
                        try:
                            time.sleep(0.2)  # Extra delay for problematic lines
                            instr.write(clean_line)
                        except:
                            print(f"Skipping problematic line {line_num}")
                            time.sleep(0.1)
        
        # End script loading
        print("Finalizing script loading...")
        time.sleep(1)
        instr.write("endscript")
        time.sleep(2)
        print("✓ Script loaded successfully")
        
        # Verify script was loaded
        try:
            test_result = instr.query(f"print({script_name} ~= nil)")
            if "true" in test_result.lower():
                print("✓ Script verified")
                return True
            else:
                print(f"⚠ Verification returned: {test_result}")
                return False
        except Exception as e:
            print(f"⚠ Verification failed: {e}")
            return False
        
    except Exception as e:
        print(f"✗ Error loading script: {e}")
        return False

def call_tsp_function(instr, function_call, timeout=300):
    """Call a TSP function and read all output with status monitoring"""
    print(f"\n{'='*60}")
    print(f"Calling TSP function: {function_call}")
    print(f"{'='*60}")
    
    # Clear any pending messages more carefully
    original_timeout = instr.timeout
    instr.timeout = 500  # Short timeout for clearing
    try:
        for _ in range(5):  # Try a few times
            try:
                instr.read()
            except:
                break  # No more pending messages
    except:
        pass
    finally:
        instr.timeout = original_timeout  # Restore original timeout
    
    # Call the function
    instr.write(function_call)
    time.sleep(0.1)  # Give instrument time to start
    
    buffer_data = []
    status = {}
    buffers = {}  # Store data organized by buffer type
    current_buffer = None
    start_time = time.time()
    consecutive_timeouts = 0
    # Increase max consecutive timeouts for long-running functions with delays
    # complete_measurement has 60s warmup + 60s stabilization + measurements
    max_consecutive_timeouts = 30 if "complete_measurement" in function_call else 3
    
    # Read all output until timeout or completion
    while (time.time() - start_time) < timeout:
        try:
            # Set timeout for individual reads - longer for complete measurements
            # complete_measurement needs longer timeout due to 60s warmup/stabilization delays
            read_timeout = 10000 if "complete_measurement" in function_call else 2000
            instr.timeout = read_timeout  # milliseconds
            line = instr.read()
            consecutive_timeouts = 0  # Reset on successful read
            
            # Check for status messages
            if line.startswith("STATUS:"):
                parts = line.split(":")
                if len(parts) >= 3:
                    status_type = parts[1]
                    status_value = ":".join(parts[2:])
                    status[status_type] = status_value
                    
                    # Display status with appropriate icon
                    if status_type == "PROGRESS":
                        print(f"⏳ {status_type}: {status_value}")
                        consecutive_timeouts = 0  # Reset on progress message
                    else:
                        print(f"📍 {status_type}: {status_value}")
                    
                    # Track which buffer is ready
                    if status_type == "BUFFER_READY":
                        current_buffer = status_value
                        buffers[current_buffer] = []
                        print(f"   → Ready to read {current_buffer}")
                        consecutive_timeouts = 0  # Reset on buffer ready
                    
                    # If function completed, break
                    if status_type == "COMPLETED":
                        print(f"✓ Function completed in {time.time() - start_time:.2f} seconds")
                        # Only break if it's the main function completion
                        if "complete_measurement" in status_value or "test_read" in status_value:
                            break
            else:
                # Regular output (likely buffer data)
                if line.strip():  # Only add non-empty lines
                    buffer_data.append(line)
                    # Also organize by buffer type if we know which buffer we're reading
                    if current_buffer and current_buffer in buffers:
                        buffers[current_buffer].append(line)
                
        except Exception as e:
            error_msg = str(e).lower()
            # Handle timeout - might mean no more data
            if "timeout" in error_msg or "vi_error_tmo" in error_msg:
                consecutive_timeouts += 1
                if consecutive_timeouts >= max_consecutive_timeouts:
                    print(f"⚠ No more data after {consecutive_timeouts} timeouts")
                    break
            # Handle query unterminated - likely no more complete messages
            elif "unterminated" in error_msg or "query" in error_msg:
                print(f"⚠ Query unterminated - end of data stream")
                break
            else:
                print(f"⚠ Error reading: {e}")
                break
    
    # Restore original timeout
    instr.timeout = original_timeout
    
    return buffer_data, status, buffers

def wait_for_script_ready(instr, timeout=100):
    """Wait for script to be loaded and ready"""
    print("Waiting for script to be ready...")
    start_time = time.time()
    
    while (time.time() - start_time) < timeout:
        try:
            instr.timeout = 1000  # 1 second timeout
            line = instr.read()
            if "STATUS:READY" in line:
                print(f"✓ Script ready: {line.strip()}")
                return True
        except:
            pass
    
    print("⚠ Script ready timeout")
    return False

def update_tsp_parameters(instr, params):
    """Update TSP script parameters with Python override values"""
    print("\nUpdating TSP script parameters on instrument...")
    
    # Map of Python parameter names to TSP variable names
    # Only update parameters that can be changed dynamically
    # NOTE: measurement_delay is NOT included because it's always calculated from other parameters
    updatable_params = {
        # Measurement Parameters
        'HeatingPower': 'HeatingPower',
        'HeatingTime': 'HeatingTime',
        'NPLC': 'NPLC',
        'DriftTime': 'DriftTime',
        'measurement_points': 'measurement_points',
        'TRIGGER_OVERHEAD': 'TRIGGER_OVERHEAD',  # Empirical trigger overhead adjustment
        
        # Thermal Parameters
        'TCR': 'TCR',
        'SampleTemperature': 'SampleTemperature',
        'THERMAL_EQUILIBRIUM_TIME': 'THERMAL_EQUILIBRIUM_TIME',
        
        # Sensor Configuration
        'SensorDesign': 'SensorDesign',
        'CableType': 'CableType',
        'InsulationType': 'InsulationType',
        'HolderType': 'HolderType',
        'AvailableProbingDepth': 'AvailableProbingDepth',
        
        # Schedule Parameters
        'PreMeasurementDelay': 'PreMeasurementDelay',
        'MeasurementInterval': 'MeasurementInterval',
        
        # Analysis Parameters
        'AnalysisType': 'AnalysisType',
        'MinIntervalSize': 'MinIntervalSize',
        'FullIntervalSize': 'FullIntervalSize',
        'SelectionStartIndex': 'SelectionStartIndex',
        'SelectionEndIndex': 'SelectionEndIndex',
        
        # Calculation Parameters
        'SpecHeatCapOfSensor': 'SpecHeatCapOfSensor',
        'SpecificHeatOfSample': 'SpecificHeatOfSample',
        'SpecHeatCapSensorCal': 'SpecHeatCapSensorCal',
        'UseDefaultSpecHeatCapSensor': 'UseDefaultSpecHeatCapSensor',
        'TimeCorrection': 'TimeCorrection',
        'CalculationID': 'CalculationID',
        
        # System Parameters
        'PowerLineFrequency': 'PowerLineFrequency',
        'SoftwareVersion': 'SoftwareVersion',
    }
    
    updated_count = 0
    for py_name, tsp_name in updatable_params.items():
        if py_name in params:
            value = params[py_name]
            # Format the value appropriately
            if isinstance(value, bool):
                tsp_value = 'true' if value else 'false'
            elif isinstance(value, str):
                tsp_value = f'"{value}"'
            else:
                tsp_value = str(value)
            
            try:
                instr.write(f"{tsp_name} = {tsp_value}")
                updated_count += 1
                time.sleep(0.05)  # Small delay between updates
            except Exception as e:
                print(f"⚠ Warning: Could not update {tsp_name}: {e}")
    
    # After updating parameters, recalculate measurement_delay on the instrument
    # This ensures the TSP script uses the correct calculated delay including trigger overhead
    try:
        instr.write("measurement_time_per_point = NPLC / PowerLineFrequency")
        time.sleep(0.05)
        instr.write("measurement_delay = HeatingTime/(measurement_points-1) - measurement_time_per_point - TRIGGER_OVERHEAD")
        time.sleep(0.05)
        print(f"✓ Recalculated measurement_delay on instrument")
    except Exception as e:
        print(f"⚠ Warning: Could not recalculate measurement_delay: {e}")
    
    print(f"✓ Updated {updated_count} parameters on instrument")
    return True

def parse_tsp_parameters(tsp_file):
    """Parse TSP file to extract configuration parameters"""
    # Start with default values - these are used if not found in TSP file
    params = {
        'TCR': 0.00503145,
        'SensorDesign': 5501,
        'CableType': 'GreyCable',
        'HeatingPower': 1.5,
        'HeatingTime': 10,
        'SampleTemperature': 21.0,
        'DriftTime': 40,
        'PreMeasurementDelay': 10,
        'MeasurementInterval': 10,
        'NPLC': 1,
        'PowerLineFrequency': 50,
        'SoftwareVersion': '7.8 Beta 7',
        'AvailableProbingDepth': 20,
        'InsulationType': 'Kapton',
        'HolderType': 'CableDirectlyConnectedToSensor',
        'AnalysisType': 'Standard',
        'MinIntervalSize': 20,
        'FullIntervalSize': 60,
        'SelectionStartIndex': 10,
        'SelectionEndIndex': 200,
        'SpecHeatCapOfSensor': 0.0063995923422626,
        'SpecificHeatOfSample': 1E-06,
        'SpecHeatCapSensorCal': True,
        'UseDefaultSpecHeatCapSensor': True,
        'TimeCorrection': True,
        'CalculationID': 1,
        'THERMAL_EQUILIBRIUM_TIME': 600,  # Default: 10 minutes between measurements
        'measurement_points': 201,  # Number of data points for transient measurement
        'TRIGGER_OVERHEAD': 0.021,  # Empirically measured trigger overhead per measurement (seconds)
        # NOTE: measurement_delay is NOT in defaults - it's always calculated from other parameters
    }
    
    if not os.path.exists(tsp_file):
        print(f"⚠ Warning: TSP file not found: {tsp_file}. Using default parameters.")
        return params
    
    try:
        with open(tsp_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # Parse numeric parameters
            numeric_patterns = {
                'TCR': r'local TCR\s*=\s*([0-9.]+)',
                'SensorDesign': r'local SensorDesign\s*=\s*(\d+)',
                'HeatingPower': r'local HeatingPower\s*=\s*([0-9.]+)',
                'HeatingTime': r'local HeatingTime\s*=\s*([0-9.]+)',
                'SampleTemperature': r'local SampleTemperature\s*=\s*([0-9.]+)',
                'DriftTime': r'local DriftTime\s*=\s*(\d+)',
                'PreMeasurementDelay': r'local PreMeasurementDelay\s*=\s*(\d+)',
                'MeasurementInterval': r'local MeasurementInterval\s*=\s*(\d+)',
                'NPLC': r'local NPLC\s*=\s*([0-9.]+)',
                'PowerLineFrequency': r'local PowerLineFrequency\s*=\s*(\d+)',
                'AvailableProbingDepth': r'local AvailableProbingDepth\s*=\s*(\d+)',
                'MinIntervalSize': r'local MinIntervalSize\s*=\s*(\d+)',
                'FullIntervalSize': r'local FullIntervalSize\s*=\s*(\d+)',
                'SelectionStartIndex': r'local SelectionStartIndex\s*=\s*(\d+)',
                'SelectionEndIndex': r'local SelectionEndIndex\s*=\s*(\d+)',
                'SpecHeatCapOfSensor': r'local SpecHeatCapOfSensor\s*=\s*([0-9.]+)',
                'SpecificHeatOfSample': r'local SpecificHeatOfSample\s*=\s*([0-9.E+-]+)',
                'CalculationID': r'local CalculationID\s*=\s*(\d+)',
                'THERMAL_EQUILIBRIUM_TIME': r'local THERMAL_EQUILIBRIUM_TIME\s*=\s*(\d+)',
                'measurement_points': r'local measurement_points\s*=\s*(\d+)',
                'TRIGGER_OVERHEAD': r'TRIGGER_OVERHEAD\s*=\s*([0-9.]+)',
                # NOTE: measurement_delay is NOT parsed - it's always calculated from other parameters
            }
            
            for key, pattern in numeric_patterns.items():
                match = re.search(pattern, content)
                if match:
                    params[key] = float(match.group(1)) if '.' in match.group(1) or 'E' in match.group(1).upper() else int(match.group(1))
            
            # Parse string parameters
            string_patterns = {
                'CableType': r'local CableType\s*=\s*"([^"]+)"',
                'InsulationType': r'local InsulationType\s*=\s*"([^"]+)"',
                'HolderType': r'local HolderType\s*=\s*"([^"]+)"',
                'AnalysisType': r'local AnalysisType\s*=\s*"([^"]+)"',
                'SoftwareVersion': r'local SoftwareVersion\s*=\s*"([^"]+)"'
            }
            
            for key, pattern in string_patterns.items():
                match = re.search(pattern, content)
                if match:
                    params[key] = match.group(1)
            
            # Parse boolean parameters
            bool_patterns = {
                'SpecHeatCapSensorCal': r'local SpecHeatCapSensorCal\s*=\s*(true|false)',
                'UseDefaultSpecHeatCapSensor': r'local UseDefaultSpecHeatCapSensor\s*=\s*(true|false)',
                'TimeCorrection': r'local TimeCorrection\s*=\s*(true|false)'
            }
            
            for key, pattern in bool_patterns.items():
                match = re.search(pattern, content)
                if match:
                    params[key] = match.group(1).lower() == 'true'
        
        print(f"✓ Parsed parameters from {tsp_file}")
        return params
        
    except Exception as e:
        print(f"⚠ Warning: Error parsing TSP file: {e}. Using default parameters.")
        return params

def generate_hotb_xml(params, all_measurements, num_iterations):
    """Generate complete .hotb XML file from measurement data"""
    
    # Generate Schedule section
    schedule_xml = f"""  <Schedule>
    <BasicPreMeasurementDelay>{params['PreMeasurementDelay']}</BasicPreMeasurementDelay>
    <BasicMeasurementInterval>{params['MeasurementInterval']}</BasicMeasurementInterval>
    <BasicNoOfMeasurements>{num_iterations}</BasicNoOfMeasurements>
    <StandbyTemperature>-1</StandbyTemperature>
    <StandbyVariation>-1</StandbyVariation>
    <ControllerStandbyMode>Undefined</ControllerStandbyMode>
    <StandbyPressure>-1</StandbyPressure>
    <StandbyPressureVariation>-1</StandbyPressureVariation>
    <PressureControllerStandbyMode>Undefined</PressureControllerStandbyMode>
    <ActivityList>
      <ScheduleActivity type="MeasurementTriggerEvent">
        <NoOfMeasurements>{num_iterations}</NoOfMeasurements>
        <MeasurementInterval>{params['MeasurementInterval']}</MeasurementInterval>
        <DoWaitWhenSwitchingSensor>false</DoWaitWhenSwitchingSensor>
        <ExperimentSettingsBySwitchPort>
          <ExecutedStep type="ExecutedExperiment">
            <RowNumber>0</RowNumber>
            <LastStatus>NotRun</LastStatus>
            <Data>
              <RunConfiguration>
                <MethodType>Standard</MethodType>
                <SampleIdentity>
                  <Identity>
                  </Identity>
                  <AvailableProbingDepth>{params['AvailableProbingDepth']}</AvailableProbingDepth>
                </SampleIdentity>
                <InstrumentRunConfigurations type="StandardRunConfigurations">
                  <Equipment>
                    <OptionalLabel>
                    </OptionalLabel>
                    <Part type="Sensor">
                      <SensorDesign>{params['SensorDesign']}</SensorDesign>
                      <Insulation>{params['InsulationType']}</Insulation>
                    </Part>
                    <Part type="Holder">
                      <HolderType>{params['HolderType']}</HolderType>
                    </Part>
                    <Part type="Cable">
                      <CableType>{params['CableType']}</CableType>
                    </Part>
                  </Equipment>
                  <SampleTemperatureData>
                    <Sample>{params['SampleTemperature']:.1f}</Sample>
                    <Source>ManualTemp</Source>
                    <Manual>{params['SampleTemperature']:.1f}</Manual>
                    <TCR>{params['TCR']:.6f}</TCR>
                  </SampleTemperatureData>
                  <HeatingPower>{params['HeatingPower']:.5f}</HeatingPower>
                  <HeatingTime>{int(params['HeatingTime'])}</HeatingTime>
                  <NPLC>{int(params['NPLC'])}</NPLC>
                  <DriftEnable>true</DriftEnable>
                  <DriftTime>{params['DriftTime']}</DriftTime>
                  <ParameterWizardData>
                    <Mode>HotDiskList</Mode>
                    <Name>StainlessSteel</Name>
                  </ParameterWizardData>
                </InstrumentRunConfigurations>
                <ExperimentHardware>
                  <HotDiskAnalyzerModel>TPS500</HotDiskAnalyzerModel>
                  <PowerLineFrequency>{params['PowerLineFrequency']}</PowerLineFrequency>
                </ExperimentHardware>
                <OriginalFile>C:\\HotDiskTPS_7\\Results\\TPS500-Test-2.hotb</OriginalFile>
                <SoftwareVersion>{params['SoftwareVersion']}</SoftwareVersion>
              </RunConfiguration>
            </Data>
            <FileName>
            </FileName>
          </ExecutedStep>
        </ExperimentSettingsBySwitchPort>
      </ScheduleActivity>
    </ActivityList>
  </Schedule>"""
    
    # Generate ExecutedStep XML for each measurement
    result_steps = []
    for iteration, meas_data in enumerate(all_measurements, start=1):
        result_steps.append(generate_executed_step_xml(params, meas_data, iteration, num_iterations, iteration == 1))
    
    result_steps_xml = "\n".join(result_steps)
    
    # Complete XML structure
    hotb_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<ExperimentBatch xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  
  <!-- ========================================== -->
  <!-- SCHEDULE SECTION - MEASUREMENT PLANNING -->
  <!-- ========================================== -->
{schedule_xml}
  <!-- ========================================== -->
  <!-- EXECUTED STEPS SECTION - MEASUREMENT HISTORY -->
  <!-- ========================================== -->
  <ExecutedSteps>
    <!-- <Executed Steps> Initial calculation step with analysis settings </Executed Steps> -->
  </ExecutedSteps>
  
  <!-- ========================================== -->
  <!-- RESULT STEPS SECTION - MEASUREMENT DATA -->
  <!-- ========================================== -->
  <ResultSteps>
    <!-- <Result Steps> Measurement data will be added here </Result Steps> -->
{result_steps_xml}
  </ResultSteps>
  
  <!-- ========================================== -->
  <!-- EXPORT AND LOG FILES SECTION -->
  <!-- ========================================== -->
  <ExportFiles />
  <LogFiles>
    <string>C:\\HotDiskTPS_7\\data\\Log\\StartHotDisk 2025 07 16 09.19.41.log</string>
  </LogFiles>
  <StatisticsByRow>false</StatisticsByRow>
</ExperimentBatch>"""
    
    return hotb_xml

def generate_executed_step_xml(params, meas_data, iteration, total_iterations, is_first):
    """Generate ExecutedStep XML for a single measurement iteration"""
    
    # Extract buffer data
    r0_data = meas_data.get('R0_defbuffer1', [])
    drift_data = meas_data.get('Drift_defbuffer2', [])
    transient_data = meas_data.get('Transient_defbuffer1', [])
    
    # Parse buffer data into arrays
    def parse_buffer_data(buffer_lines):
        timestamps, voltages, currents = [], [], []
        for line in buffer_lines:
            parts = line.strip().split(',')
            if len(parts) == 3:
                try:
                    timestamps.append(float(parts[0]))
                    voltages.append(float(parts[1]))
                    currents.append(float(parts[2]))
                except:
                    pass
        return timestamps, voltages, currents
    
    r0_timestamps, r0_voltages, r0_currents = parse_buffer_data(r0_data)
    drift_timestamps, drift_voltages, drift_currents = parse_buffer_data(drift_data)
    trans_timestamps, trans_voltages, trans_currents = parse_buffer_data(transient_data)
    
    # Calculate R0
    r0_value = 0
    if r0_voltages and r0_currents:
        r0_values = [v / c for v, c in zip(r0_voltages, r0_currents) if c != 0]
        if r0_values:
            r0_value = sum(r0_values) / len(r0_values)
    
    # Generate timestamp
    current_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.0000000+02:00")
    
    # Generate signals
    drift_signal = generate_signal_xml("Drift", drift_timestamps, drift_voltages, drift_currents)
    trans_signal = generate_signal_xml("Transient", trans_timestamps, trans_voltages, trans_currents)
    
    # Description
    description = f"Performing measurement {iteration} of {total_iterations}, each {int(params['HeatingTime'])}s long with {params['HeatingPower']:.3f}W Sample Temperature {params['SampleTemperature']:.1f} °C User Value\\nTCR {params['TCR']:.6f} K⁻¹ TCR-values.txt Sample Pressure Unknown"
    
    # CalcSettings (only for first result)
    calc_settings = ""
    if is_first:
        calc_settings = f"""
        <CalcSettings>
          <selectionStartIndex>{params['SelectionStartIndex']}</selectionStartIndex>
          <selectionEndIndex>{params['SelectionEndIndex']}</selectionEndIndex>
          <specHeatCapOfSensor>{params['SpecHeatCapOfSensor']:.15g}</specHeatCapOfSensor>
          <specificHeatOfSample>{params['SpecificHeatOfSample']:.1g}</specificHeatOfSample>
          <specificHeatOfSampleKnown>false</specificHeatOfSampleKnown>
          <specHeatCapSensorCal>{str(params['SpecHeatCapSensorCal']).lower()}</specHeatCapSensorCal>
          <UseDefaultSpecHeatCapSensor>{str(params['UseDefaultSpecHeatCapSensor']).lower()}</UseDefaultSpecHeatCapSensor>
          <timeCorrection>{str(params['TimeCorrection']).lower()}</timeCorrection>
          <analysisType>{params['AnalysisType']}</analysisType>
          <MinIntervalSize>{params['MinIntervalSize']}</MinIntervalSize>
          <FullIntervalSize>{params['FullIntervalSize']}</FullIntervalSize>
          <CalculationID>{params['CalculationID']}</CalculationID>
        </CalcSettings>"""
    
    # FileName
    file_name = f"_{iteration}" if is_first else f"_Row0.{iteration-1}.0"
    
    # LastStatus
    last_status = "Executed Calculated" if is_first else "Executed"
    
    # Description fields (omit for first result)
    desc_fields = "" if is_first else f"      <Description>{description}</Description>\\n      <DefaultDescription>{description}</DefaultDescription>\\n"
    
    # Full ExecutedStep XML
    executed_step_xml = f"""
    <ExecutedStep type="ExecutedExperiment">
      <RowNumber>{iteration}</RowNumber>
      <LastStatus>{last_status}</LastStatus>
{desc_fields}      <Time>{current_time}</Time>
      <Data>
        <RunConfiguration>
          <MethodType>Standard</MethodType>
          <SampleIdentity>
            <Identity></Identity>
            <AvailableProbingDepth>{params['AvailableProbingDepth']}</AvailableProbingDepth>
          </SampleIdentity>
          <InstrumentRunConfigurations type="StandardRunConfigurations">
            <Equipment>
              <OptionalLabel>
              </OptionalLabel>
              <Part type="Sensor">
                <SensorDesign>{params['SensorDesign']}</SensorDesign>
                <Insulation>{params['InsulationType']}</Insulation>
              </Part>
              <Part type="Holder">
                <HolderType>{params['HolderType']}</HolderType>
              </Part>
              <Part type="Cable">
                <CableType>{params['CableType']}</CableType>
              </Part>
            </Equipment>
            <SampleTemperatureData>
              <Sample>{params['SampleTemperature']:.1f}</Sample>
              <Source>ManualTemp</Source>
              <Manual>{params['SampleTemperature']:.1f}</Manual>
              <TCR>{params['TCR']:.6f}</TCR>
            </SampleTemperatureData>
            <HeatingPower>{params['HeatingPower']:.5f}</HeatingPower>
            <HeatingTime>{int(params['HeatingTime'])}</HeatingTime>
            <NPLC>{int(params['NPLC'])}</NPLC>
            <DriftEnable>true</DriftEnable>
            <DriftTime>{params['DriftTime']}</DriftTime>
            <ParameterWizardData>
              <Mode>HotDiskList</Mode>
              <Name>StainlessSteel</Name>
            </ParameterWizardData>
          </InstrumentRunConfigurations>
          <ExperimentHardware>
            <HotDiskAnalyzerModel>TPS500</HotDiskAnalyzerModel>
            <PowerLineFrequency>{params['PowerLineFrequency']}</PowerLineFrequency>
          </ExperimentHardware>
          <ExpTimestamp>{current_time}</ExpTimestamp>
          <OriginalFile>C:\\HotDiskTPS_7\\Results\\TPS500-Test-2.hotb</OriginalFile>
          <SoftwareVersion>{params['SoftwareVersion']}</SoftwareVersion>
        </RunConfiguration>{calc_settings}
        <MeasurementData>
          <Measurements>
{drift_signal}
{trans_signal}
          </Measurements>
          <TheBridgeMeasurementsBalanced>
            <Sensor_ur>{r0_value:.10g}</Sensor_ur>
            <Reference_urs>0</Reference_urs>
            <timestamp>0</timestamp>
          </TheBridgeMeasurementsBalanced>
          <TheBridgeMeasurementsDrift>
            <Reference_urs>0</Reference_urs>
            <timestamp>0</timestamp>
          </TheBridgeMeasurementsDrift>
          <TheBridgeMeasurementsTransient>
            <Reference_urs>0</Reference_urs>
            <timestamp>0</timestamp>
          </TheBridgeMeasurementsTransient>
        </MeasurementData>
      </Data>
      <FileName>{file_name}</FileName>
    </ExecutedStep>"""
    
    return executed_step_xml

def generate_signal_xml(signal_type, timestamps, voltages, currents):
    """Generate Signal XML for drift or transient data"""
    
    # Generate timestamp array
    timestamp_xml = "<timestamps>\n"
    for t in timestamps:
        timestamp_xml += f"  <double>{t:.10g}</double>\n"
    timestamp_xml += "</timestamps>\n"
    
    # Generate voltage array
    voltage_xml = "<voltages>\n"
    for v in voltages:
        voltage_xml += f"  <double>{v:.10g}</double>\n"
    voltage_xml += "</voltages>\n"
    
    # Generate current array
    current_xml = "<currents>\n"
    for c in currents:
        current_xml += f"  <double>{c:.10g}</double>\n"
    current_xml += "</currents>\n"
    
    signal_xml = f"""<Signal type="VoltCurrentSignal">
  <signalType>{signal_type}</signalType>
{timestamp_xml}{voltage_xml}{current_xml}</Signal>"""
    
    return signal_xml