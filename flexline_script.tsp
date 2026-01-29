-- Simplified TSP Script for Thermal Constants Analysis using Keithley 2450
-- Result saving moved to Python script using printbuffer
--
-- FUNCTION AVAILABILITY SYSTEM:
-- ============================
-- Functions are defined in this script but NOT immediately callable from outside.
-- You MUST run this script first using: myworkers.run()
-- After running, functions become globally available and Python can call them.
--
-- STATUS SIGNALING SYSTEM:
-- ========================
-- Functions signal their status to Python using print statements:
--   STATUS:READY - Script is ready, functions are available
--   STATUS:STARTED:function_name - Function execution started
--   STATUS:BUFFER_READY:buffer_name - Buffer has data and is ready to read
--   STATUS:BUFFER_SIZE:N - Number of readings in buffer
--   STATUS:COMPLETED:function_name - Function execution completed
--
-------change these values as needed-----------------------------------
-- NOTE: GLOBAL variables (no 'local') are updated from Python at runtime
-- Only parameters actually used by this script are declared here.
HeatingPower = 1.5
HeatingTime = 10
NPLC = 1
PowerLineFrequency = 50
measurement_points = 201
TRIGGER_OVERHEAD = 0.021
measurement_time_per_point = NPLC / PowerLineFrequency
measurement_delay = HeatingTime/(measurement_points-1) - measurement_time_per_point - TRIGGER_OVERHEAD

local BASELINE_STABILIZATION_TIME = 60
local COOLING_TIME = 60
local BASELINE_MEASUREMENTS = 50
local BASELINE_TOLERANCE = 0.001
local SENSOR_WARMUP_TIME = 60
local MEASUREMENT_QUALITY_CHECKS = true

----------------------------------------------------------------------

-- ENHANCED: Function to assess measurement quality
local function assess_measurement_quality(readings, expected_range)
    if not MEASUREMENT_QUALITY_CHECKS then
        return 1.0, "Quality checks disabled"
    end
    
    local quality_score = 1.0
    local notes = ""
    
    -- Check for zero or invalid readings
    local zero_count = 0
    local total_count = 0
    for _, reading in ipairs(readings) do
        total_count = total_count + 1
        if reading == 0 or reading == nil then
            zero_count = zero_count + 1
        end
    end
    
    if zero_count > total_count * 0.1 then
        quality_score = quality_score * 0.5
        notes = notes .. "High number of zero readings; "
    end
    
    -- Check for reasonable range
    local avg_reading = 0
    local valid_count = 0
    for _, reading in ipairs(readings) do
        if reading ~= 0 and reading ~= nil then
            avg_reading = avg_reading + reading
            valid_count = valid_count + 1
        end
    end
    
    if valid_count > 0 then
        avg_reading = avg_reading / valid_count
        
        -- Check if average is within expected range
        if expected_range and (avg_reading < expected_range.min or avg_reading > expected_range.max) then
            quality_score = quality_score * 0.7
            notes = notes .. "Average reading outside expected range; "
        end
    end
    
    return quality_score, notes
end

-- ENHANCED: Function to check baseline stability with quality assessment
local function check_baseline_stability(iteration)
    print(string.format("Checking baseline stability for iteration %d...", iteration))
    
    reset() 
    errorqueue.clear()
    defbuffer1.clear()

    smu.source.output = smu.OFF 
    smu.measure.sense = smu.SENSE_4WIRE
    smu.source.func = smu.FUNC_DC_VOLTAGE
    smu.measure.func = smu.FUNC_DC_CURRENT
    smu.source.autorange = smu.OFF
    smu.measure.autorange = smu.OFF
    smu.source.range = 0.02
    smu.measure.range = 0.03
    smu.source.level = 0.01
    smu.source.ilimit.level = 0.03
    smu.measure.nplc = 2
    smu.measure.autozero.enable = smu.OFF

    smu.source.output = smu.ON
    
    -- Take multiple baseline measurements with averaging
    local baseline_readings = {}
    local total_resistance = 0
    local valid_count = 0
    local quality_readings = {}
    
    for i = 1, BASELINE_MEASUREMENTS do
        local reading = smu.measure.read()
        local voltage = smu.source.level
        local current = reading
        local timestamp = timer.gettime()
        
        if current ~= 0 then
            local resistance = voltage / current
            table.insert(baseline_readings, resistance)
            table.insert(quality_readings, current)
            total_resistance = total_resistance + resistance
            valid_count = valid_count + 1
            

            print(string.format("Baseline %d: %.6e Ohms", i, resistance))
        end
        
        delay(0.1)  -- Small delay between readings
    end
    
    smu.source.output = smu.OFF
    
    if valid_count < BASELINE_MEASUREMENTS * 0.8 then
        print("Warning: Insufficient valid baseline readings")
        return false, 0, 0.0
    end
    
    -- Calculate average and check stability
    local avg_resistance = total_resistance / valid_count
    local max_deviation = 0
    
    for _, resistance in ipairs(baseline_readings) do
        local deviation = math.abs(resistance - avg_resistance) / avg_resistance
        if deviation > max_deviation then
            max_deviation = deviation
        end
    end
    
    local is_stable = max_deviation <= BASELINE_TOLERANCE
    local quality_score, notes = assess_measurement_quality(quality_readings, {min = 0.001, max = 0.03})
    
    print(string.format("Baseline stability check: Avg=%.6e, MaxDev=%.6f%%, Stable=%s, Quality=%.3f", 
        avg_resistance, max_deviation * 100, tostring(is_stable), quality_score))
    

    
    return is_stable, avg_resistance, quality_score
end


-- ENHANCED: Function to perform thermal stabilization with sensor warmup
local function perform_thermal_stabilization(iteration)
    print(string.format("Performing thermal stabilization for iteration %d...", iteration))
    print(string.format("Waiting %d seconds for thermal equilibrium...", BASELINE_STABILIZATION_TIME))
    
    -- Turn off all outputs and wait for thermal equilibrium
    smu.source.output = smu.OFF
    
    -- NEW: Sensor warmup period
    if iteration == 1 then
        print(string.format("Initial sensor warmup: %d seconds", SENSOR_WARMUP_TIME))
        print("STATUS:PROGRESS:Sensor warmup in progress...")
        delay(SENSOR_WARMUP_TIME)
        print("STATUS:PROGRESS:Sensor warmup completed")
    end
    
    -- Wait for thermal stabilization
    print("STATUS:PROGRESS:Thermal stabilization in progress...")
    delay(BASELINE_STABILIZATION_TIME)
    print("STATUS:PROGRESS:Thermal stabilization wait completed")
    
    -- Check baseline stability with quality assessment
    local is_stable, baseline_resistance, quality_score = check_baseline_stability(iteration)
    
    if not is_stable then
        print(string.format("Warning: Baseline not stable for iteration %d. Quality score: %.3f", iteration, quality_score))
    else
        print(string.format("Baseline stable for iteration %d. Resistance: %.6e Ohms, Quality: %.3f", 
            iteration, baseline_resistance, quality_score))
    end
    
    return baseline_resistance, quality_score
end

function test_read(iteration)
    -- Signal function start to Python
    print("STATUS:STARTED:test_read")
    
    reset() 
    --errorqueue.clear()
    defbuffer1.clear()
    format.data = format.ASCII
    format.asciiprecision = 6

    smu.source.output = smu.OFF -- Ensure output is off initially
    smu.measure.sense = smu.SENSE_4WIRE -- Common setting

    smu.source.func = smu.FUNC_DC_VOLTAGE
    smu.measure.func = smu.FUNC_DC_CURRENT -- Set functions first
    smu.source.autorange = smu.OFF      -- Disable source autorange
    smu.measure.autorange = smu.OFF     -- Ensure measure autorange is off
    smu.source.range = 0.02             -- Set source range
    smu.measure.range = 0.03            -- Set measure range
    smu.source.level = 0.01             -- Set source level
    smu.source.ilimit.level = 0.03      -- Set source limit
    smu.measure.nplc = 2
    smu.measure.autozero.enable = smu.OFF

    smu.source.output = smu.ON
    
    trigger.model.load("SimpleLoop", 6, 0.25, defbuffer1) 
    trigger.model.initiate()
    waitcomplete()
    
    -- Signal buffer is ready
    print("STATUS:BUFFER_READY:defbuffer1")
    print(string.format("STATUS:BUFFER_SIZE:%d", defbuffer1.n))
    
    -- Print buffer data - one line per reading
    for i = 1, defbuffer1.n do
        print(string.format("%.5e,%.5e,%.5e", 
            defbuffer1.relativetimestamps[i], 
            defbuffer1.sourcevalues[i], 
            defbuffer1.readings[i]))
    end

    smu.source.output = smu.OFF
    
    -- Signal completion
    print("STATUS:COMPLETED:test_read")
end 

-- COMPLETE MEASUREMENT FUNCTION: Runs full measurement sequence
function complete_measurement(iteration)
    print("STATUS:STARTED:complete_measurement")
    print(string.format("Starting complete measurement sequence for iteration %d", iteration))
    
    -- Step 1: Thermal Stabilization
    print(string.format("\n=== Step 1: Thermal Stabilization (iteration %d) ===", iteration))
    local baseline_resistance, baseline_quality = perform_thermal_stabilization(iteration)
    print(string.format("Thermal stabilization completed. Baseline: %.6e Ohms, Quality: %.3f", 
        baseline_resistance, baseline_quality))
    
    -- Step 2: Measure R0
    print(string.format("\n=== Step 2: Measure R0 (iteration %d) ===", iteration))
    print("STATUS:STARTED:measure_R0")
    
    reset()
    defbuffer1.clear()
    format.data = format.ASCII
    format.asciiprecision = 6

    smu.source.output = smu.OFF
    smu.measure.sense = smu.SENSE_4WIRE
    smu.source.func = smu.FUNC_DC_VOLTAGE
    smu.measure.func = smu.FUNC_DC_CURRENT
    smu.source.autorange = smu.OFF
    smu.measure.autorange = smu.OFF
    smu.source.range = 0.02
    smu.measure.range = 0.03
    smu.source.level = 0.01
    smu.source.ilimit.level = 0.03
    smu.measure.nplc = 2
    smu.measure.autozero.enable = smu.OFF

    smu.source.output = smu.ON
    print("STATUS:PROGRESS:Taking 6 R0 readings (approx 2 seconds)...")
    trigger.model.load("SimpleLoop", 6, 0.25, defbuffer1)
    trigger.model.initiate()
    waitcomplete()

    -- Signal R0 buffer is ready
    print("STATUS:BUFFER_READY:R0_defbuffer1")
    print(string.format("STATUS:BUFFER_SIZE:%d", defbuffer1.n))
    
    -- Calculate R0
    local total_resistance = 0
    local valid_count = 0
    local current_R0 = 0
    
    for i = 1, defbuffer1.n do
        local voltage = defbuffer1.sourcevalues[i]
        local current = defbuffer1.readings[i]
        if current ~= 0 then
            local resistance = voltage / current
            total_resistance = total_resistance + resistance
            valid_count = valid_count + 1
        end
    end
    
    if valid_count > 0 then
        current_R0 = total_resistance / valid_count
        print(string.format("R0 calculated: %.6e Ohms (from %d readings)", current_R0, valid_count))
    end
    
    -- Print R0 buffer data - one line per reading
    for i = 1, defbuffer1.n do
        print(string.format("%.5e,%.5e,%.5e", 
            defbuffer1.relativetimestamps[i], 
            defbuffer1.sourcevalues[i], 
            defbuffer1.readings[i]))
    end
    
    smu.source.output = smu.OFF
    print("STATUS:COMPLETED:measure_R0")
    
    -- Step 3: Drift Measurement
    print(string.format("\n=== Step 3: Drift Measurement (iteration %d) ===", iteration))
    print("STATUS:STARTED:perform_drift_measurement")
    
    reset()
    defbuffer2.clear()
    
    smu.source.output = smu.OFF
    smu.measure.sense = smu.SENSE_4WIRE
    smu.source.func = smu.FUNC_DC_VOLTAGE
    smu.measure.func = smu.FUNC_DC_CURRENT
    smu.source.autorange = smu.OFF
    smu.measure.autorange = smu.OFF
    smu.source.range = 0.02
    smu.measure.range = 0.03
    smu.source.level = 0.01
    smu.source.ilimit.level = 0.03
    smu.measure.nplc = 2
    smu.measure.autozero.enable = smu.OFF

    smu.source.output = smu.ON
    print("STATUS:PROGRESS:Taking 101 drift readings (approx 40 seconds)...")
    trigger.model.load("SimpleLoop", 101, 0.4, defbuffer2)
    trigger.model.initiate()
    waitcomplete()

    -- Signal drift buffer is ready
    print("STATUS:BUFFER_READY:Drift_defbuffer2")
    print(string.format("STATUS:BUFFER_SIZE:%d", defbuffer2.n))
    print(string.format("Drift measurement completed: %d readings", defbuffer2.n))
    
    -- Print drift buffer data - one line per reading
    for i = 1, defbuffer2.n do
        print(string.format("%.5e,%.5e,%.5e", 
            defbuffer2.relativetimestamps[i], 
            defbuffer2.sourcevalues[i], 
            defbuffer2.readings[i]))
    end
    
    smu.source.output = smu.OFF
    print("STATUS:COMPLETED:perform_drift_measurement")
    
    -- Step 4: Transient Measurement
    print(string.format("\n=== Step 4: Transient Measurement (iteration %d) ===", iteration))
    print("STATUS:STARTED:perform_transient_measurement")
    
    reset()
    defbuffer1.clear()
    
    local voltage_source = math.sqrt(HeatingPower * current_R0)
    print(string.format("Heating voltage calculated: %.6f V (from R0=%.6e, Power=%.2f)", 
        voltage_source, current_R0, HeatingPower))
    
    smu.source.output = smu.OFF
    smu.source.func = smu.FUNC_DC_VOLTAGE
    smu.measure.func = smu.FUNC_DC_CURRENT
    smu.source.autorange = smu.OFF
    smu.measure.autorange = smu.OFF
    smu.source.range = 20
    smu.measure.range = 1.05
    smu.source.level = voltage_source
    smu.source.ilimit.level = 1.05
    smu.measure.nplc = NPLC
    smu.measure.sense = smu.SENSE_4WIRE
    smu.measure.autozero.enable = smu.OFF

    smu.source.output = smu.ON
    print(string.format("STATUS:PROGRESS:Taking 201 transient readings at %.1fW heating power...", HeatingPower))
    trigger.model.load("SimpleLoop", measurement_points, measurement_delay, defbuffer1) --data point, delay btw heatingtime/points 
    trigger.model.initiate()
    waitcomplete()

    -- Signal transient buffer is ready
    print("STATUS:BUFFER_READY:Transient_defbuffer1")
    print(string.format("STATUS:BUFFER_SIZE:%d", defbuffer1.n))
    print(string.format("Transient measurement completed: %d readings", defbuffer1.n))
    
    -- Print transient buffer data - one line per reading
    for i = 1, defbuffer1.n do
        print(string.format("%.5e,%.5e,%.5e", 
            defbuffer1.relativetimestamps[i], 
            defbuffer1.sourcevalues[i], 
            defbuffer1.readings[i]))
    end
    
    smu.source.output = smu.OFF
    print("STATUS:COMPLETED:perform_transient_measurement")
    
    -- Cooling period
    print(string.format("Cooling period: %d seconds", COOLING_TIME))
    print("STATUS:PROGRESS:Cooling in progress...")
    delay(COOLING_TIME)
    print("STATUS:PROGRESS:Cooling completed")
    
    print(string.format("\n=== Complete Measurement Sequence Finished (iteration %d) ===", iteration))
    print("STATUS:COMPLETED:complete_measurement")
end

-- Command handler - listens for commands from Python
-- This makes functions callable after script is loaded and run
print("STATUS:READY:Waiting for commands...")

-- Simple command to test if script is responsive
function ping()
    print("STATUS:PONG")
end

-- Main execution based on commands (optional)
-- Uncomment below if you want to run specific function on script load
-- complete_measurement(0)
