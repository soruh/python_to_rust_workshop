def do_work(implementation):
    """
    This function defines the workload.
    'implementation' is the function being tested (either the Python or Rust version).
    """

    return implementation(180)


def compare_results(result_a, result_b):
    """
    Defines how to verify that the Rust version matches the Python version.
    """
    return result_a == result_b
