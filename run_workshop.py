import subprocess
import sys
import time
import importlib.util
from pathlib import Path

try:
    from colorama import init, Fore, Style
except ImportError:
    # Fallback if colorama isn't installed
    class DummyColor:
        def __getattr__(self, name):
            return ""

    init = lambda **kwargs: None
    Fore = Style = DummyColor()

# Initialize colorama to auto-reset colors after each print
init(autoreset=True)

# locations of the rust/python implementation
PYTHON_LIB_PATH = Path("./python_lib")
RUST_LIB_PATH = Path("./rust_lib")


def install_package(path, is_rust=False):
    """Installs a package in editable mode (or via maturin for Rust)."""

    print(f"Building and installing {path.name:<10} ...", end="", flush=True)

    if is_rust:
        cmd = [
            "maturin",
            "develop",
            "--release",
            "--manifest-path",
            str(path / "Cargo.toml"),
        ]
    else:
        cmd = [sys.executable, "-m", "pip", "install", "-e", str(path)]

    result = subprocess.run(cmd, capture_output=True, text=True)

    # 3. Print the result on the SAME line
    if result.returncode != 0:
        print(f"{Fore.RED} FAILED")
        print(f"{Fore.RED}Error details:\n{result.stderr}")
        sys.exit(1)

    print(f"{Fore.GREEN} DONE")


def load_workshop_config():
    """Dynamically loads the workshop_config.py file."""
    spec = importlib.util.spec_from_file_location(
        "workshop_config", "workshop_config.py"
    )
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config


def benchmark(name, func, workload_func, target_total_duration=5.0):
    # Use Cyan for the header of the specific benchmark
    print(f"    {Style.DIM}Calibrating {name}...", end="", flush=True)

    # --- Stage 1: Calibration ---
    # Determine how many iterations fit into ~0.1s
    start_cal = time.perf_counter()
    count = 0
    while time.perf_counter() - start_cal < 0.1:
        workload_func(func)
        count += 1

    # Chunk size targets ~0.2s of work
    chunk_size = max(1, int(count * 2.0))

    print(f" {Fore.GREEN}DONE")

    # --- Stage 2: High-Precision Measurement ---
    print(
        f"    {Style.DIM}Running in chunks of {Style.RESET_ALL}{Fore.MAGENTA}{chunk_size:,} {Style.RESET_ALL}{Style.DIM}iterations...",
        end="",
        flush=True,
    )

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

    print(
        f" {Fore.GREEN}DONE{Style.RESET_ALL}{Style.DIM} (Completed {Style.RESET_ALL}{Fore.MAGENTA}{total_iterations:,} {Style.RESET_ALL}{Style.DIM}iterations)"
    )

    print(
        f"    Result: {Style.BRIGHT}{avg_time:.8f} sec/iter {Style.NORMAL}{Style.DIM}(Overhead: {overhead:.1f}%)"
    )
    return avg_time


def main():
    print(f"{Style.BRIGHT}{Fore.CYAN}=== Install Phase ===")

    # 1. Install/Build both libraries
    install_package(PYTHON_LIB_PATH, is_rust=False)
    install_package(RUST_LIB_PATH, is_rust=True)

    # 2. Load User Config
    try:
        config = load_workshop_config()
    except FileNotFoundError:
        print(f"{Fore.RED}Could not find 'workshop_config.py'.")
        sys.exit(1)

    # 3. Import the installed libraries
    try:
        import python_lib
        import rust_lib
    except ImportError as e:
        print(f"{Fore.RED}Could not import libraries: {e}")
        print(
            f"{Fore.YELLOW}Ensure you are running in a virtual environment where 'maturin' is installed."
        )
        sys.exit(1)

    # 4. Get the functions
    py_func = python_lib.implementation
    rs_func = rust_lib.implementation

    print(f"\n{Style.BRIGHT}{Fore.CYAN}=== Verification Phase ===")
    py_res = config.do_work(py_func)

    if not config.compare_results(py_res, py_res):
        print(
            f"{Fore.RED}The python result does not match itself! Check your `compare_results` implementation"
        )
        print(f"Python result: {py_res}")
        sys.exit(1)

    rs_res = config.do_work(rs_func)

    if config.compare_results(py_res, rs_res):
        print(f"Results {Fore.GREEN}Match!")
    else:
        print(f"Results {Fore.RED}Do Not Match!")
        print(f"Python result: {py_res}")
        print(f"  Rust result: {rs_res}")
        sys.exit(1)

    print(f"\n{Style.BRIGHT}{Fore.CYAN}=== Benchmark Phase ===")
    py_time = benchmark("Python", py_func, config.do_work)
    rs_time = benchmark("Rust", rs_func, config.do_work)

    speedup = py_time / rs_time

    if speedup > 1:
        print(
            f"\nThe rust implementation is approximately {Fore.GREEN}{Style.BRIGHT}{speedup:.2f}x faster{Style.RESET_ALL} than Python!"
        )
    else:
        slowdown = 1 / speedup
        print(
            f"\nThe rust implementation is approximately {Fore.RED}{Style.BRIGHT}{slowdown:.2f}x slower{Style.RESET_ALL} than Python!"
        )


if __name__ == "__main__":
    main()
