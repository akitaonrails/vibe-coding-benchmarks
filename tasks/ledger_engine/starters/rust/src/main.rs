mod device;
mod domain;
mod index;
mod solution;
mod transaction;

use std::io::{self, BufRead, Write};

fn main() {
    let mut service = solution::Solution::default();
    let stdin = io::stdin();
    let mut stdout = io::stdout().lock();
    for line in stdin.lock().lines() {
        let request = serde_json::from_str(&line.expect("read JSONL request"))
            .expect("contract guarantees valid JSON");
        let response = service.call(request);
        writeln!(stdout, "{response}").expect("write JSONL response");
        stdout.flush().expect("flush response");
    }
}
