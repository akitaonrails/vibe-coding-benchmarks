mod solution;
use std::io::{self, BufRead, Write};
fn main() {
    let mut solution = solution::Solution::new();
    for line in io::stdin().lock().lines() {
        let request = serde_json::from_str(&line.unwrap()).unwrap();
        println!("{}", solution.call(request));
        io::stdout().flush().unwrap();
    }
}
