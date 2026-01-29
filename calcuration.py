#!/usr/bin/env python3
import os
import socket
import time
import re
import matplotlib.pyplot as plt
import numpy as np
from dotenv import load_dotenv

load_dotenv()

# Configuration (socket.connect requires port as int)
HOTDISK_IP = os.getenv('HOTDISK_IP')
_raw = os.getenv('HOTDISK_PORT', '50000')
HOTDISK_PORT = int(_raw) if _raw else 50000


class HotDiskError(Exception):
    """Raised when HotDisk connection fails or file cannot be opened."""
    pass


def send_visa_command(command, timeout=30):
    """
    Send VISA command to HotDisk software.
    Raises HotDiskError if connection fails or EXP:OPEN cannot open the file.
    """
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)

        print(f"\n→ Connecting to HotDisk at {HOTDISK_IP}:{HOTDISK_PORT}...")
        sock.connect((HOTDISK_IP, HOTDISK_PORT))
        print("✓ Connected to HotDisk!")

        # Format command for HotDisk (needs \r\n terminator)
        if not command.endswith('\r\n') and not command.endswith('\r'):
            command += '\r\n'  # HotDisk uses CRLF

        print(f"→ Sending VISA command: {command.strip()}")
        sock.sendall(command.encode('utf-8'))
        print(f"→ Waiting for response (timeout: {timeout}s)...")

        time.sleep(0.5)

        try:
            response = sock.recv(4096)

            if response:
                response_str = response.decode('utf-8', errors='replace').strip()
                print(f"✓ HotDisk response ({len(response)} bytes): {response_str}")

                # Stop if EXP:OPEN failed (file not found or error)
                if command.strip().upper().startswith("EXP:OPEN"):
                    if _is_open_error(response_str):
                        raise HotDiskError(
                            f"Cannot open file. HotDisk response: {response_str!r}"
                        )

                return response_str
            else:
                print("(no response from HotDisk)")
                if command.strip().upper().startswith("EXP:OPEN"):
                    raise HotDiskError("Cannot open file: no response from HotDisk")
                return None
        except socket.timeout:
            print(f"✗ Timeout after {timeout}s - HotDisk not responding")
            raise HotDiskError(
                f"HotDisk not responding after {timeout}s. "
                "Check command or that HotDisk is running."
            )

    except ConnectionRefusedError:
        print(f"✗ Connection refused - HotDisk software not running on port {HOTDISK_PORT}")
        raise HotDiskError(
            f"Cannot connect to HotDisk at {HOTDISK_IP}:{HOTDISK_PORT}. "
            "Is HotDisk software running?"
        )
    except socket.timeout:
        print(f"✗ Connection timeout after {timeout}s")
        raise HotDiskError(
            f"Cannot connect to HotDisk at {HOTDISK_IP}:{HOTDISK_PORT} (timeout). "
            "Check IP and that HotDisk is running."
        )
    except HotDiskError:
        raise
    except Exception as e:
        print(f"✗ Error: {e}")
        raise HotDiskError(f"HotDisk communication failed: {e}")
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass


def _is_open_error(response_str):
    """True if HotDisk response indicates EXP:OPEN failed (file not found / error)."""
    if not response_str:
        return True
    r = response_str.lower()
    return (
        "error" in r
        or "not found" in r
        or "failed" in r
        or "cannot open" in r
        or "invalid" in r
        or r.startswith("-")  # some SCPI errors start with -4xx
    )


def send_hotdisk_commands():
    """Send common HotDisk commands"""
    
    commands = [
        "*IDN?",           # Identification
        "*RST",            # Reset
        "SYST:ERR?",       # System error
        "MEAS:VOLT?",      # Measure voltage
        "CONF:VOLT",       # Configure voltage
    ]
    
    print("\n" + "="*70)
    print("Sending Common HotDisk Commands")
    print("="*70)
    
    for cmd in commands:
        print(f"\n--- Sending: {cmd} ---")
        send_visa_command(cmd)
        time.sleep(1)


def interactive_hotdisk():
    """Interactive mode for HotDisk commands"""
    print("\n" + "="*70)
    print("Interactive HotDisk Command Mode")
    print("="*70)
    print("Send commands to HotDisk software")
    print("Type 'quit' to exit")
    print("\nCommon HotDisk commands:")
    print("  *IDN?         - Query identification")
    print("  *RST          - Reset")
    print("  MEAS:VOLT?    - Measure voltage")
    print("  CONF:VOLT     - Configure voltage")
    print("  SYST:ERR?     - Query system error")
    print("="*70)
    
    while True:
        try:
            cmd = input("\nHotDisk> ").strip()
            
            if cmd.lower() in ['quit', 'exit', 'q']:
                print("Disconnecting from HotDisk...")
                break
            
            if not cmd:
                continue
            
            send_visa_command(cmd)
            
        except KeyboardInterrupt:
            print("\n\nInterrupted")
            break


def test_hotdisk_connection():
    """Test connection to HotDisk software"""
    print(f"\n→ Testing connection to HotDisk at {HOTDISK_IP}:{HOTDISK_PORT}...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((HOTDISK_IP, HOTDISK_PORT))
        sock.close()
        
        print(f"✓ SUCCESS! HotDisk software is reachable")
        return True
        
    except ConnectionRefusedError:
        print(f"✗ Connection refused")
        print(f"   → HotDisk software not running on {HOTDISK_IP}:{HOTDISK_PORT}")
        print(f"   → Check if HD software is started")
        print(f"   → Verify port {HOTDISK_PORT} is correct")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def parse_numeric_data(response):
    """
    Parse numeric data from HotDisk response
    Returns list of numbers found in the response
    """
    if not response:
        return []
    
    sanitized = response.replace(',', '.')
    # Find all numbers (integers and floats) in the response
    numbers = re.findall(r'-?\d+\.?\d*[eE]?[+-]?\d*', sanitized)
    
    # Convert to floats
    try:
        return [float(n) for n in numbers]
    except:
        return []


def parse_data_pairs(response):
    """
    Parse data pairs (x,y) or comma-separated values from response
    Returns tuples of (x_values, y_values) if pairs found, else (None, values)
    """
    if not response:
        return None, None
    
    sanitized = response.replace(',', '.')
    # Try to find comma-separated pairs (e.g., "1.0,2.0" or "x=1.0,y=2.0")
    pairs = re.findall(r'[-+]?\d+\.?\d*[eE]?[+-]?\d*', sanitized)
    
    if len(pairs) >= 2:
        # Check if we have pairs or just a list of numbers
        values = [float(p) for p in pairs if p]
        
        if len(values) >= 2:
            # If odd length, drop the last entry so we keep full pairs
            usable_length = len(values) - (len(values) % 2)
            if usable_length >= 2:
                x_vals = values[:usable_length:2]
                y_vals = values[1:usable_length:2]
                if x_vals and y_vals:
                    return x_vals, y_vals
        
        # Fallback: treat values as single series
        return list(range(len(values))), values
    
    return None, None


def adjust_axis_range(ax, x_data, y_data, padding=0.05):
    """
    Adjust axis range based on data with padding
    padding: percentage of range to add as padding (default 5%)
    """
    if x_data and y_data:
        x_min, x_max = min(x_data), max(x_data)
        y_min, y_max = min(y_data), max(y_data)
        
        # Calculate padding
        x_range = x_max - x_min
        y_range = y_max - y_min
        
        # Handle case where range is zero
        if x_range == 0:
            x_range = abs(x_min) * 0.1 if x_min != 0 else 1
        if y_range == 0:
            y_range = abs(y_min) * 0.1 if y_min != 0 else 1
        
        # Add padding
        x_padding = x_range * padding
        y_padding = y_range * padding
        
        # Set axis limits
        ax.set_xlim(x_min - x_padding, x_max + x_padding)
        ax.set_ylim(y_min - y_padding, y_max + y_padding)
    elif x_data:
        # Only x_data (y_data is indices)
        x_min, x_max = min(x_data), max(x_data)
        x_range = x_max - x_min
        if x_range == 0:
            x_range = abs(x_min) * 0.1 if x_min != 0 else 1
        x_padding = x_range * padding
        ax.set_xlim(x_min - x_padding, x_max + x_padding)
        # y-axis is indices, so set reasonable range
        if len(x_data) > 0:
            ax.set_ylim(-0.5, len(x_data) - 0.5)


def create_graphs(calc_response, res_response, drift_response=None, trans_response=None):
    """
    Create graphs from EXP:CALC?, EXP:RES?, and EXP:DRIFT? responses
    """
    print("\n" + "="*70)
    print("Creating Graphs from Results")
    print("="*70)
    
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    calc_fig = None
    calc_filename = None

    # Parse data
    calc_numbers = parse_numeric_data(calc_response) if calc_response else []
    res_numbers = parse_numeric_data(res_response) if res_response else []
    drift_numbers = parse_numeric_data(drift_response) if drift_response else []
    trans_numbers = parse_numeric_data(trans_response) if trans_response else []
    
    calc_x, calc_y = parse_data_pairs(calc_response) if calc_response else (None, None)
    res_x, res_y = parse_data_pairs(res_response) if res_response else (None, None)
    drift_x, drift_y = parse_data_pairs(drift_response) if drift_response else (None, None)
    trans_x, trans_y = parse_data_pairs(trans_response) if trans_response else (None, None)

    
    # Create figure with up to 4 subplots
    fig, axes = plt.subplots(4, 1, figsize=(10, 16))
    fig.suptitle('HotDisk Measurement Results', fontsize=14, fontweight='bold')
    
    # Plot EXP:TRANS? data (scatter plot with normal axes)
    ax1 = axes[0]
    if trans_x and trans_y:
        ax1.scatter(trans_x, trans_y, color='purple', marker='o', s=50, label='EXP:TRANS Data', alpha=0.7)
        ax1.set_xlabel('X Values', fontsize=10)
        ax1.set_ylabel('Y Values', fontsize=10)
        adjust_axis_range(ax1, trans_x, trans_y)
    elif trans_numbers:
        indices = list(range(len(trans_numbers)))
        ax1.scatter(indices, trans_numbers, color='purple', marker='o', s=50, label='EXP:TRANS Values', alpha=0.7)
        ax1.set_xlabel('Index', fontsize=10)
        ax1.set_ylabel('Values', fontsize=10)
        adjust_axis_range(ax1, indices, trans_numbers)
    else:
        ax1.text(0.5, 0.5, 'No numeric data found in EXP:TRANS? response', 
                ha='center', va='center', transform=ax1.transAxes, fontsize=12)
        ax1.set_xlabel('No Data', fontsize=10)
        ax1.set_ylabel('No Data', fontsize=10)
    
    ax1.set_title('EXP:TRANS? - Transient Data (Scatter Plot)', fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    handles, labels = ax1.get_legend_handles_labels()
    if handles:
        ax1.legend()
    
    # Plot EXP:CALC? data (scatter plot with normal axes)
    ax2 = axes[1]
    if calc_x and calc_y:
        ax2.scatter(calc_x, calc_y, color='blue', marker='o', s=50, label='EXP:CALC Data', alpha=0.7)
        ax2.set_xlabel('X Values', fontsize=10)
        ax2.set_ylabel('Y Values', fontsize=10)
        adjust_axis_range(ax2, calc_x, calc_y)
    elif calc_numbers:
        indices = list(range(len(calc_numbers)))
        ax2.scatter(indices, calc_numbers, color='blue', marker='o', s=50, label='EXP:CALC Values', alpha=0.7)
        ax2.set_xlabel('Index', fontsize=10)
        ax2.set_ylabel('Values', fontsize=10)
        adjust_axis_range(ax2, indices, calc_numbers)
    else:
        ax2.text(0.5, 0.5, 'No numeric data found in EXP:CALC? response', 
                ha='center', va='center', transform=ax2.transAxes, fontsize=12)
        ax2.set_xlabel('No Data', fontsize=10)
        ax2.set_ylabel('No Data', fontsize=10)
    
    ax2.set_title('EXP:CALC? - Calculation Results (Scatter Plot)', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    handles, labels = ax2.get_legend_handles_labels()
    if handles:
        ax2.legend()
    
    # Plot EXP:DRIFT? data (scatter plot with normal axes)
    ax3 = axes[2]
    if drift_x and drift_y:
        ax3.scatter(drift_x, drift_y, color='green', marker='o', s=50, label='EXP:DRIFT Data', alpha=0.7)
        ax3.set_xlabel('X Values', fontsize=10)
        ax3.set_ylabel('Y Values', fontsize=10)
        adjust_axis_range(ax3, drift_x, drift_y)
    elif drift_numbers:
        indices = list(range(len(drift_numbers)))
        ax3.scatter(indices, drift_numbers, color='green', marker='o', s=50, label='EXP:DRIFT Values', alpha=0.7)
        ax3.set_xlabel('Index', fontsize=10)
        ax3.set_ylabel('Values', fontsize=10)
        adjust_axis_range(ax3, indices, drift_numbers)
    else:
        ax3.text(0.5, 0.5, 'No numeric data found in EXP:DRIFT? response', 
                ha='center', va='center', transform=ax3.transAxes, fontsize=12)
        ax3.set_xlabel('No Data', fontsize=10)
        ax3.set_ylabel('No Data', fontsize=10)

    ax3.set_title('EXP:DRIFT? - Drift Data (Scatter Plot)', fontsize=12, fontweight='bold')
    ax3.grid(True, alpha=0.3)
    handles, labels = ax3.get_legend_handles_labels()
    if handles:
        ax3.legend()

    # Plot EXP:RES? data (scatter plot with normal axes)
    ax4 = axes[3]
    if res_x and res_y:
        ax4.scatter(res_x, res_y, color='red', marker='o', s=50, label='EXP:RES Data', alpha=0.7)
        ax4.set_xlabel('X Values', fontsize=10)
        ax4.set_ylabel('Y Values', fontsize=10)
        adjust_axis_range(ax4, res_x, res_y)
    elif res_numbers:
        indices = list(range(len(res_numbers)))
        ax4.scatter(indices, res_numbers, color='red', marker='o', s=50, label='EXP:RES Values', alpha=0.7)
        ax4.set_xlabel('Index', fontsize=10)
        ax4.set_ylabel('Values', fontsize=10)
        adjust_axis_range(ax4, indices, res_numbers)
    else:
        ax4.text(0.5, 0.5, 'No numeric data found in EXP:RES? response', 
                ha='center', va='center', transform=ax4.transAxes, fontsize=12)
        ax4.set_xlabel('No Data', fontsize=10)
        ax4.set_ylabel('No Data', fontsize=10)

    ax4.set_title('EXP:RES? - Results (Scatter Plot)', fontsize=12, fontweight='bold')
    ax4.grid(True, alpha=0.3)
    handles, labels = ax4.get_legend_handles_labels()
    if handles:
        ax4.legend()
    
    # Adjust layout
    plt.tight_layout()
    
    # Save figure
    filename = f"hotdisk_results_{timestamp}.png"
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"\n✓ Graph saved to: {filename}")
    
    # Show graph
    plt.show()
    
    print("✓ Graph displayed!")

    if calc_fig and calc_filename:
        print(f"✓ Additional EXP:CALC? line plot saved to: {calc_filename}")
    return filename

