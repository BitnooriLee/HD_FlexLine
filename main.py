#!/usr/bin/env python3
import os
import shutil
import sys
import time
import traceback
from datetime import datetime
from dotenv import load_dotenv
from parameters import experiment_parameters as params

from tps_measurement import (
    connect_to_instrument,
    load_tsp_script,
    parse_tsp_parameters,
    update_tsp_parameters,
    wait_for_script_ready,
    call_tsp_function,
    generate_hotb_xml,
)
from calcuration import send_visa_command, create_graphs, HotDiskError

load_dotenv()
INSTRUMENT_IP = os.getenv("TPS_IP")
SCRIPT_NAME = os.getenv("SCRIPT_NAME")
TSP_FILE = "flexline_script.tsp"
SERVER_PATH = os.getenv("SERVER_PATH")
CLIENT_PATH = os.getenv("CLIENT_PATH_TO_RESULT_FILE")
NUM_ITERATIONS = params["NUM_ITERATIONS"]

def run_tps_measurement():
    print("TPS Measurement")
    print("=" * 60)

    try:
        measurement_time_per_point = params["NPLC"] / params["PowerLineFrequency"]
        params["measurement_delay"] = (
            params["HeatingTime"] / (params["measurement_points"] - 1)
            - measurement_time_per_point
            - params["TRIGGER_OVERHEAD"]
        )

        print("\n✓ Measurement parameters:")
        print(f"  - HeatingPower: {params['HeatingPower']} W")
        print(f"  - HeatingTime: {params['HeatingTime']} s")
        print(f"  - NPLC: {params['NPLC']}")
        print(f"  - TCR: {params['TCR']} K⁻¹")
        print(f"  - SampleTemperature: {params['SampleTemperature']} °C")
        print(f"  - measurement_points: {params['measurement_points']}")
        print(f"  - measurement_delay: {params['measurement_delay']:.6f} s (calculated)")
        print(f"  - ThermalEquilibriumTime: {params['THERMAL_EQUILIBRIUM_TIME']} s ({params['THERMAL_EQUILIBRIUM_TIME']/60:.1f} min)")
        print(f"  - SensorDesign: {params['SensorDesign']}")
        print(f"  - AnalysisType: {params['AnalysisType']}")

        instr = connect_to_instrument(INSTRUMENT_IP)
        if not instr:
            print("✗ Failed to connect to instrument. Exiting.")
            return False, None

        if not load_tsp_script(instr, SCRIPT_NAME, TSP_FILE):
            print("✗ Failed to load TSP script. Exiting.")
            instr.close()
            return False, None

        print(f"\nRunning script '{SCRIPT_NAME}' to initialize functions...")
        instr.write(f"{SCRIPT_NAME}.run()")
        time.sleep(0.5)

        if not wait_for_script_ready(instr, timeout=100):
            print("⚠ Warning: Script may not be ready, continuing anyway...")

        update_tsp_parameters(instr, params)

        print("\nTesting function availability...")
        try:
            instr.write("ping()")
            time.sleep(0.2)
            response = instr.read()
            if "PONG" in response:
                print("✓ Functions are available")
            else:
                print(f"⚠ Unexpected response: {response}")
        except Exception as e:
            print(f"⚠ Ping test failed: {e}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        date_str = datetime.now().strftime("%Y%m%d")
        results_folder = f"measurement_results_{date_str}"
        folder_existed = os.path.isdir(results_folder)
        os.makedirs(results_folder, exist_ok=True)
        if folder_existed:
            print(f"\n✓ Adding results to existing folder: {results_folder}")
        else:
            print(f"\n✓ Created results folder: {results_folder}")

        all_measurements = []

        for iteration in range(1, NUM_ITERATIONS + 1):
            print(f"\n{'='*60}")
            print(f"MEASUREMENT ITERATION {iteration} of {NUM_ITERATIONS}")
            print(f"{'='*60}")
            print("Note: Thermal stabilization is performed automatically inside complete_measurement")

            print(f"\nRunning complete_measurement({iteration})...")
            buffer_data, status, buffers = call_tsp_function(
                instr,
                f"complete_measurement({iteration})",
                timeout=1200,
            )

            print(f"\nResults Summary for Iteration {iteration}:")
            print(f"Status: {status}")
            print(f"Total output lines: {len(buffer_data)}")

            if buffers:
                print("Buffer Data Collected:")
                for buffer_name, data in buffers.items():
                    print(f"  - {buffer_name}: {len(data)} lines")

            complete_file = os.path.join(results_folder, f"complete_measurement_iter{iteration}.txt")
            with open(complete_file, "w") as f:
                f.write(f"Complete Measurement Sequence - Iteration {iteration}\n")
                f.write(f"Timestamp: {timestamp}\n")
                f.write(f"Status: {status}\n")
                f.write(f"{'='*60}\n\n")
                for line in buffer_data:
                    f.write(line + "\n")
            print(f"  ✓ Complete log: complete_measurement_iter{iteration}.txt")

            buffer_file_mapping = {
                "R0_defbuffer1": f"R0_measurement_iter{iteration}.txt",
                "Drift_defbuffer2": f"drift_measurement_iter{iteration}.txt",
                "Transient_defbuffer1": f"transient_measurement_iter{iteration}.txt",
            }

            for buffer_name, data in buffers.items():
                filename = buffer_file_mapping.get(buffer_name, f"{buffer_name}_iter{iteration}.txt")
                filepath = os.path.join(results_folder, filename)

                with open(filepath, "w") as f:
                    f.write("Timestamp(s),Voltage(V),Current(A)\n")
                    for line in data:
                        parts = line.strip().split(",")
                        if len(parts) == 3:
                            try:
                                timestamp_val = parts[0].strip()
                                voltage_val = parts[1].strip()
                                current_val = parts[2].strip()
                                if "e" in timestamp_val.lower() or "." in timestamp_val:
                                    f.write(f"{timestamp_val},{voltage_val},{current_val}\n")
                            except Exception:
                                pass

                print(f"  ✓ {buffer_name}: {filename} ({len(data)} readings)")

            all_measurements.append(buffers)
            print(f"✓ Iteration {iteration} completed and saved")

            if iteration < NUM_ITERATIONS:
                thermal_equilibrium_time = int(params["THERMAL_EQUILIBRIUM_TIME"])
                minutes = thermal_equilibrium_time / 60
                print(f"\n⏳ Waiting {thermal_equilibrium_time} seconds ({minutes:.1f} minutes) for thermal equilibrium before next iteration...")
                print("   This ensures thermal stability between measurements")
                time.sleep(thermal_equilibrium_time)
                print("✓ Thermal equilibrium period completed")

        print(f"\n{'='*60}")
        print("GENERATING .hotb FILE")
        print(f"{'='*60}")

        hotb_filepath = os.path.join(results_folder, f"Result_{timestamp}.hotb")
        hotb_xml = generate_hotb_xml(params, all_measurements, NUM_ITERATIONS)

        with open(hotb_filepath, "w", encoding="utf-8") as f:
            f.write(hotb_xml)

        print(f"✓ Generated .hotb file: {hotb_filepath}")
        print(f"  - Contains {NUM_ITERATIONS} measurement iterations")
        print("  - All parameters from TSP script included")
        print("  - Ready for import into HotDisk software")

        print(f"\n{'='*60}")
        print("MEASUREMENT SEQUENCE COMPLETED")
        print(f"{'='*60}")
        print(f"✓ All results saved to folder: {results_folder}/")
        print("  Files created:")
        print(f"    - Result_{timestamp}.hotb (main result file)")
        for i in range(1, NUM_ITERATIONS + 1):
            print(f"    - complete_measurement_iter{i}.txt")
            print(f"    - R0_measurement_iter{i}.txt")
            print(f"    - drift_measurement_iter{i}.txt")
            print(f"    - transient_measurement_iter{i}.txt")

        instr.write("reset()")
        instr.close()
        print("\n✓ Connection closed")

        return True, hotb_filepath

    except Exception as e:
        print(f"✗ Error: {e}")
        traceback.print_exc()
        return False, None


def run_calcuration(hotb_filename):
    """HotDisk calculation flow: send VISA commands and optionally create graphs.
    Stops on HotDiskError (connection failed or file could not be opened)."""
    print("\n" + "=" * 70)
    print("Sending Commands to HotDisk")
    print("=" * 70)

    try:
        print("\n1. Sending *IDN? command...")
        send_visa_command("*IDN?")

        print("\n2. Sending EXP:OPEN command...")
        hotb_path = os.path.join(SERVER_PATH or "", hotb_filename)
        send_visa_command(f"EXP:OPEN {hotb_path}")

        print("\n" + "=" * 70)
        print("Sending Command Sequence")
        print("=" * 70)

        commands = [
            ("EXP:TRANS?", "Query transient data"),
            ("EXP:DRIFT?", "Query drift data"),
            ("ROW:SEL 0-9", "Select all rows"),
            ("CALC:EXE FINE", "Execute fine calculation"),
            (f"EXPORT {hotb_path.replace('.hotb', '.xlsx')}", "Export results to Excel file"),
        ]

        trans_response = None
        calc_response = None
        res_response = None
        drift_response = None

        for i, (cmd, description) in enumerate(commands, 3):
            print(f"\n{i}. Sending {cmd} ({description})...")
            response = send_visa_command(cmd)

            if cmd == "EXP:TRANS?":
                trans_response = response
            elif cmd == "EXP:CALC?":
                calc_response = response
            elif cmd == "EXP:RES?":
                res_response = response
            elif cmd == "EXP:DRIFT?":
                drift_response = response

            time.sleep(0.5)

        print("\n" + "=" * 70)
        print("All commands sent!")
        print("=" * 70)

        if calc_response or res_response or drift_response or trans_response:
            try:
                create_graphs(calc_response, res_response, drift_response, trans_response)
            except ImportError:
                print("\n⚠️  matplotlib not installed. Install it with:")
                print("   pip3 install matplotlib numpy")
            except Exception as e:
                print(f"\n✗ Error creating graphs: {e}")
        else:
            print("\n⚠️  No data available for graphing")

    except HotDiskError as e:
        print(f"\n✗ Stopping: {e}")
        raise


def send_result_file(hotb_filepath):
    """Copy the .hotb file from run_tps_measurement() to CLIENT_PATH as Result_{timestamp}.hotb.
    Returns (True, result_filename) on success, (False, None) on failure."""
    if not hotb_filepath or not os.path.isfile(hotb_filepath):
        print("⚠ No result file to save (measurement did not produce a .hotb file).")
        return False, None

    if not CLIENT_PATH:
        print("⚠ CLIENT_PATH_TO_RESULT_FILE_PATH not set in .env; skipping copy to client path.")
        return False, None

    # measurement_results_20250129_123456.hotb -> Result_20250129_123456.hotb
    base = os.path.basename(hotb_filepath)
    if base.startswith("measurement_results_") and base.endswith(".hotb"):
        timestamp = base.replace("measurement_results_", "").replace(".hotb", "")
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_filename = f"Result_{timestamp}.hotb"
    dest_path = os.path.join(CLIENT_PATH, result_filename)

    os.makedirs(CLIENT_PATH, exist_ok=True)
    shutil.copy2(hotb_filepath, dest_path)

    print(f"✓ Result file saved to: {dest_path}")
    return True, result_filename

def main():
    """Run TPS measurement then HotDisk calculation. Edit to run only one if needed."""
    success, hotb_filepath = run_tps_measurement()
    hotb_filename = None
    if success and hotb_filepath:
        _, hotb_filename = send_result_file(hotb_filepath)
    if hotb_filename:
        try:
            run_calcuration(hotb_filename)
        except HotDiskError as e:
            print(f"\n✗ HotDisk failed: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
