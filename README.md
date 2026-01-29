# HD FlexLine

Thermal measurement and analysis pipeline: run TPS measurements on a Keithley 2450, generate `.hotb` files, copy results to a shared path, and run HotDisk calculation/export.

---

## Install requirements

```bash
# Create and use a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**Requirements:**

| Package        | Purpose                          |
|----------------|----------------------------------|
| pyvisa         | Keithley 2450 (TCP/IP)           |
| python-dotenv  | Load `.env` config               |
| matplotlib     | HotDisk result graphs            |
| numpy          | Numerics for graphs              |
| pytest         | Run tests (optional)             |

---

## .env configuration

Create a `.env` file in the project root (copy from `.env.example` if present). **Do not commit `.env`** (it is in `.gitignore`).

| Variable                     | Required | Description |
|-----------------------------|----------|-------------|
| `TPS_IP`                    | Yes      | Keithley 2450 IP (e.g. `192.168.169.97`) |
| `SCRIPT_NAME`               | Yes      | TSP script name loaded on instrument (e.g. `myworkers`) |
| `HOTDISK_IP`                | Yes      | HotDisk software host IP (e.g. `192.168.169.96`) |
| `HOTDISK_PORT`              | Yes      | HotDisk TCP port, integer (e.g. `50000`) |
| `SERVER_PATH`               | Yes      | Path where HotDisk opens `.hotb` and exports (e.g. `Z:/Bitnoori/`). Must be valid on the HotDisk machine. |
| `CLIENT_PATH_TO_RESULT_FILE`| Yes      | Local/shared folder where result `.hotb` is copied (e.g. `/Volumes/ShareNoBackup/Bitnoori/` or `Z:/Bitnoori/`) |
| `CLIENT_IP`                 | No       | Optional client identifier |
| `SCRIPT_NAME`               | No       | TSP script name loaded on instrument (e.g. `myworkers`) |

---

## How to start

### Full pipeline (measurement → send measurement result file to server → HotDisk software → send calculation result file to server)

```bash
python main.py
```

Runs in order:

1. **TPS measurement** – Connect to Keithley, load `flexline_script.tsp`, run measurement iterations, write `.hotb` under `measurement_results_YYYYMMDD/`.
2. **Copy result** – Copy the generated `.hotb` to `CLIENT_PATH_TO_RESULT_FILE` as `Result_YYYYMMDD_HHMMSS.hotb`.
3. **HotDisk** – Connect to HotDisk, open that file at `SERVER_PATH`, run commands (EXP:TRANS?, EXP:DRIFT?, CALC:EXE FINE, EXPORT), optionally plot.

If HotDisk connection or file open fails, the program exits with code 1.

### Test individual steps

```bash
# TPS measurement only (needs instrument)
python test_main.py --tps

# Copy a .hotb file to CLIENT_PATH only
python test_main.py --send-result {filepath}

# HotDisk only (open file and run commands; HotDisk must be running)
python test_main.py --calcuration {filename}
```

### Run tests

```bash
pytest tests/ -v
```

---

## Overall workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           HD FlexLine workflow                                │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────────┐     TCP/IP      ┌─────────────────────┐
  │  Python (main)   │ ◄──────────────► │  Keithley 2450       │
  │  tps_measurement │                  │  flexline_script.tsp │
  └────────┬─────────┘                  └─────────────────────┘
           │
           │ 1. Parse TSP params, connect, load script
           │ 2. Run complete_measurement(1..N) iterations
           │ 3. Collect buffers (R0, Drift, Transient)
           │ 4. Generate .hotb XML
           ▼
  ┌──────────────────┐
  │ measurement_     │   Date-based folder (e.g. measurement_results_20250129)
  │ results_YYYYMMDD │   • measurement_results_YYYYMMDD_HHMMSS.hotb
  │   *.hotb, *.txt  │   • R0/drift/transient logs per iteration
  └────────┬─────────┘
           │
           │ 5. Copy .hotb to CLIENT_PATH
           ▼
  ┌──────────────────┐
  │ CLIENT_PATH      │   Result_YYYYMMDD_HHMMSS.hotb
  │ (shared/local)   │   (same file must be visible at SERVER_PATH on HotDisk PC)
  └────────┬─────────┘
           │
           │ 6. HotDisk: EXP:OPEN SERVER_PATH/Result_*.hotb
           │ 7. EXP:TRANS?, EXP:DRIFT?, CALC:EXE FINE, EXPORT *.xlsx
           ▼
  ┌──────────────────┐     TCP/IP      ┌─────────────────────┐
  │  Python           │ ◄──────────────► │  HotDisk software   │
  │  calcuration      │   :50000        │  (open file, calc,  │
  │  send_visa_command│                  │   export Excel)     │
  └────────┬─────────┘                  └─────────────────────┘
           │
           │ 8. Optional: create_graphs() from responses
           ▼
  ┌──────────────────┐
  │  Plots / Excel   │   On HotDisk machine (SERVER_PATH)
  └──────────────────┘

  On connection or EXP:OPEN failure → HotDiskError → exit 1 (stop).
```

**Summary:**

| Step | Where | What |
|------|--------|------|
| 1–4 | Keithley 2450 | TSP script runs; Python gets buffers and builds `.hotb` in `measurement_results_YYYYMMDD/`. |
| 5 | This PC / share | Copy that `.hotb` to `CLIENT_PATH` as `Result_<timestamp>.hotb`. |
| 6–7 | HotDisk PC | HotDisk opens `SERVER_PATH/Result_<timestamp>.hotb`, runs analysis, exports Excel. |
| 8 | Python | Optional graphs from HotDisk responses. |

Ensure the file at `CLIENT_PATH` is the same as the one HotDisk sees at `SERVER_PATH` (e.g. same network share or synced path).

---

## Project layout

```
HD_FlexLine/
├── main.py              # Entry: run_tps_measurement → send_result_file → run_calcuration
├── tps_measurement.py    # Keithley connect, TSP load, parse params, generate .hotb
├── calcuration.py        # HotDisk VISA commands, graphs; HotDiskError on failure
├── flexline_script.tsp   # TSP script for Keithley (measurement logic)
├── test_main.py          # CLI to test TPS / send-result / calcuration separately
├── tests/                # Pytest tests
├── requirements.txt
├── .env                  # Not committed; see “.env configuration” above
└── README.md
```

---

## Notes

- **Keithley**: Must be on the same network; `TPS_IP` and `SCRIPT_NAME` in `.env` must match your setup.
- **HotDisk**: Must be running and listening on `HOTDISK_PORT`. `SERVER_PATH` must be a path HotDisk can read (e.g. `Z:/Bitnoori/` on the HotDisk machine).
- **Paths**: `CLIENT_PATH_TO_RESULT_FILE` is where this script writes the copy; `SERVER_PATH` is the path HotDisk uses to open that file (often the same share with different mount/style).
