mod domain;mod repository;mod worker;mod solution;
use std::io::{self,BufRead,Write};
fn main(){let mut s=solution::Solution::default();let stdin=io::stdin();let mut out=io::stdout().lock();for line in stdin.lock().lines(){let q=serde_json::from_str(&line.unwrap()).unwrap();writeln!(out,"{}",s.call(q)).unwrap();out.flush().unwrap();}}
