use serde_json::{json, Value};
pub struct Solution;
impl Solution {
    pub fn new() -> Self { Self }
    pub fn call(&mut self, _request: Value) -> Value { json!({"error":"unimplemented"}) }
}
