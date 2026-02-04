/// A pure Rust function to compute the `n`th fibonacci number or None
/// if it does not fit into a u128
///
/// Python will no be able to see this function unless you expose it in a `pyo3::pymodule`
fn fibonacci(n: u32) -> Option<u128> {
    let mut a: u128 = 0;
    let mut b: u128 = 1;

    for _ in 0..n {
        (a, b) = (b, a.checked_add(b)?);
    }

    Some(a)
}

/// The module which will be exposed to python
/// all functions declared as `#[pyfunction]`s in here will
/// be visible from python
#[pyo3::pymodule]
mod rust_lib {
    use super::*;

    use pyo3::exceptions::PyOverflowError;
    use pyo3::prelude::*;

    #[pyfunction]
    fn implementation(n: u32) -> PyResult<u128> {
        fibonacci(n).ok_or_else(|| {
            PyOverflowError::new_err(format!(
                "Overflow occured while computing the {n}th fibonacci number"
            ))
        })
    }
}
