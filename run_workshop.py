import math
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

    print(f"Building and installing {f'{path.name}...':<13}", end="", flush=True)

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
        print(f" {Fore.RED}FAILED")
        print(f"{Fore.RED}Error details:\n{result.stderr}")
        sys.exit(1)

    print(f" {Fore.GREEN}DONE")


def load_workshop_config():
    """Dynamically loads the workshop_config.py file."""
    spec = importlib.util.spec_from_file_location(
        "workshop_config", "workshop_config.py"
    )
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config


def get_time_scale(seconds):
    """Finds the best unit/multiplier based on the duration."""
    if seconds == 0:
        return "s", 1.0

    units = [("ns", 1e-9), ("µs", 1e-6), ("ms", 1e-3), ("s", 1.0)]

    # Pick the unit where the value is >= 1
    # We default to the largest unit (s) if none are smaller than 1000
    best_unit, best_mult = units[-1]
    for unit, multiplier in units:
        if seconds < multiplier * 1000:
            best_unit, best_mult = unit, multiplier
            break

    return best_unit, best_mult


def benchmark(
    name,
    func,
    workload_func,
    target_total_duration=1.0,
    force_unit=None,
    force_multiplier=None,
):
    print(f"    {Style.DIM}Calibrating {f'{name}...':<32}", end="", flush=True)

    # Check how long the function takes for a short time to check how many iterations we should run
    start_cal = time.perf_counter()
    count = 0
    while time.perf_counter() - start_cal < 0.1:
        workload_func(func)
        count += 1

    chunk_size = max(1, int(count * 2.0))
    print(f" {Fore.GREEN}DONE")

    # Actual measurement (should take approx. target_total_duration)
    print(f"{Style.DIM}    Running in chunks of ", end="")
    print(
        f"{Fore.MAGENTA}{f"{chunk_size:,}":>9}{Style.RESET_ALL} {Style.DIM}iterations...",
        end="",
        flush=True,
    )

    iteration_times = []
    total_pure_time = 0.0
    wall_clock_start = time.perf_counter()

    while (time.perf_counter() - wall_clock_start) < target_total_duration:
        chunk_start = time.perf_counter()
        for _ in range(chunk_size):
            workload_func(func)
        chunk_end = time.perf_counter()

        pure_duration = chunk_end - chunk_start
        iteration_times.append(pure_duration / chunk_size)
        total_pure_time += pure_duration

    # Compute the stddev
    total_iterations = len(iteration_times) * chunk_size
    avg_time = sum(iteration_times) / len(iteration_times)

    if len(iteration_times) > 1:
        variance = sum((x - avg_time) ** 2 for x in iteration_times) / (
            len(iteration_times) - 1
        )
        std_dev = math.sqrt(variance)
    else:
        std_dev = 0.0

    # Use forced units if provided, otherwise calculate them
    if force_unit and force_multiplier:
        unit, multiplier = force_unit, force_multiplier
    else:
        unit, multiplier = get_time_scale(avg_time)

    scaled_avg = avg_time / multiplier
    scaled_std = std_dev / multiplier

    total_wall_time = time.perf_counter() - wall_clock_start
    overhead = ((total_wall_time - total_pure_time) / total_wall_time) * 100

    # pad result to \pm is aligned in the center
    left_side = f"{scaled_avg:.3f} {unit}"
    right_side = f"{scaled_std:.3f} {unit}"
    centered_result = f"{left_side:>14} ±{right_side:>14}"

    print(f" {Fore.GREEN}DONE")
    print(
        f"    {Style.DIM}└─ Completed {Style.RESET_ALL}{Fore.MAGENTA}{total_iterations:>17,}{Style.RESET_ALL} {Style.DIM}iterations"
    )
    print(
        f"    {Style.DIM}└─ Result: {Style.RESET_ALL}{Style.BRIGHT}{centered_result} "
        f"{Style.NORMAL}{Style.DIM}   (Benchmarking Overhead: {overhead:>5.1f}%){Style.RESET_ALL}"
    )

    # Return the unit and multiplier so they can be reused
    return avg_time, unit, multiplier


def main(benchmark_duration=1.0):
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
        print(f"Python result: {config.print_result(py_res)}")
        sys.exit(1)

    rs_res = config.do_work(rs_func)

    if config.compare_results(py_res, rs_res):
        print(f"Results {Fore.GREEN}MATCH")
    else:
        print(f"Results {Fore.RED}DO NOT MATCH")
        print(f"Python result: {config.print_result(py_res)}")
        print(f"  Rust result: {config.print_result(rs_res)}")
        sys.exit(1)

    print(f"\n{Style.BRIGHT}{Fore.CYAN}=== Benchmark Phase ===")

    # Run Python and capture the scale used
    rs_time, used_unit, used_mult = benchmark(
        "Rust", rs_func, config.do_work, target_total_duration=benchmark_duration
    )

    # Run Rust using the same units as Python
    py_time, _, _ = benchmark(
        "Python",
        py_func,
        config.do_work,
        force_unit=used_unit,
        force_multiplier=used_mult,
        target_total_duration=benchmark_duration,
    )

    speedup = py_time / rs_time

    if speedup > 1:
        print(
            f"\nThe rust implementation ran {Fore.GREEN}{Style.BRIGHT}{speedup:.2f}x faster{Style.RESET_ALL} than Python!"
        )
    else:
        slowdown = 1 / speedup
        print(
            f"\nThe rust implementation ran {Fore.RED}{Style.BRIGHT}{slowdown:.2f}x slower{Style.RESET_ALL} than Python!"
        )


if __name__ == "__main__":
    main()
