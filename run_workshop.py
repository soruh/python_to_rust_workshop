import subprocess
import sys
import time
import importlib.util
from pathlib import Path

# Configuration
PYTHON_LIB_PATH = Path("./python_lib")
RUST_LIB_PATH = Path("./rust_lib")


def install_package(path, is_rust=False):
    """Installs a package in editable mode (or via maturin for Rust)."""
    print(f"🔨 Building and Installing {path.name}...")
    if is_rust:
        # maturin develop builds and installs into the current venv
        cmd = [
            "maturin",
            "develop",
            "--release",
            "--manifest-path",
            str(path / "Cargo.toml"),
        ]
    else:
        # standard pip install
        cmd = [sys.executable, "-m", "pip", "install", "-e", str(path)]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Error installing {path.name}:\n{result.stderr}")
        sys.exit(1)
    print(f"✅ {path.name} installed.")


def load_workshop_config():
    """Dynamically loads the workshop_config.py file."""
    spec = importlib.util.spec_from_file_location(
        "workshop_config", "workshop_config.py"
    )
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config


def benchmark(name, func, workload_func, target_total_duration=5.0):
    print(f"   ⏱️  Calibrating {name}...")

    # --- Stage 1: Calibration ---
    # Determine how many iterations fit into ~0.1s
    start_cal = time.perf_counter()
    count = 0
    while time.perf_counter() - start_cal < 0.1:
        workload_func(func)
        count += 1

    # Chunk size targets ~0.2s of work to balance precision vs. responsiveness
    chunk_size = max(1, int(count * 2.0))

    # --- Stage 2: High-Precision Measurement ---
    print(f"      Running in chunks of {chunk_size:,} iterations...")

    total_pure_time = 0.0
    total_iterations = 0
    wall_clock_start = time.perf_counter()

    while (time.perf_counter() - wall_clock_start) < target_total_duration:

        chunk_start = time.perf_counter()
        for _ in range(chunk_size):
            workload_func(func)
        chunk_end = time.perf_counter()

        total_pure_time += chunk_end - chunk_start
        total_iterations += chunk_size

    avg_time = total_pure_time / total_iterations

    # Calculate overhead for interest (Wall clock vs Pure execution)
    total_wall_time = time.perf_counter() - wall_clock_start
    overhead = ((total_wall_time - total_pure_time) / total_wall_time) * 100

    print(f"      Completed {total_iterations:,} iterations")
    print(f"      Result: {avg_time:.8f} sec/iter (Overhead: {overhead:.1f}%)")
    return avg_time


def main():
    print("=== 🦀 Workshop Runner Starting 🐍 ===\n")

    # 1. Install/Build both libraries
    install_package(PYTHON_LIB_PATH, is_rust=False)
    install_package(RUST_LIB_PATH, is_rust=True)

    # 2. Load User Config
    config = load_workshop_config()

    # 3. Import the installed libraries
    # (We assume the package names match the directory names for simplicity)
    try:
        import python_lib
        import rust_lib
    except ImportError as e:
        print(f"❌ Could not import libraries: {e}")
        print(
            "Ensure you are running in a virtual environment where 'maturin' is installed."
        )
        sys.exit(1)

    # 4. Get the functions
    py_func = python_lib.implementation
    rs_func = rust_lib.implementation

    print("\n=== 🧪 Verification Phase ===")
    py_res = config.do_work(py_func)

    if not config.compare_results(py_res, py_res):
        print(
            "❌ The python result does not match itself! Check your `compare_results` implementation"
        )
        print(f"Python result: {py_res}")
        sys.exit(1)

    rs_res = config.do_work(rs_func)

    if config.compare_results(py_res, rs_res):
        print("✅ Results Match! The Rust implementation is correct.")
    else:
        print("❌ Results Do Not Match!")
        print(f"Python result: {py_res}")
        print(f"  Rust result: {rs_res}")
        sys.exit(1)

    print("\n=== ⏱️  Benchmark Phase ===")
    py_time = benchmark("Python", py_func, config.do_work)
    rs_time = benchmark("Rust", rs_func, config.do_work)

    speedup = py_time / rs_time
    print(f"\n⚡ Rust is {speedup:.2f}x faster than Python!")


if __name__ == "__main__":
    main()
