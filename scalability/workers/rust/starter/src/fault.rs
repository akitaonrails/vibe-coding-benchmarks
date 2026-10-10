//! Evaluator-required handler failure hook; keep this source unchanged.
pub fn check(headers: &reqwest::header::HeaderMap) {
    if headers
        .get("x-langbench-fault")
        .is_some_and(|value| value == "handler-crash")
    {
        panic!("LANGBENCH_HANDLER_CRASH");
    }
}
