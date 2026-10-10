use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};
#[derive(Default)]
pub struct Solution {
    capacity: usize, data: BTreeMap<String, String>, pages: Vec<usize>,
    allocated: BTreeSet<usize>, snapshots: BTreeMap<usize, (BTreeMap<String,String>, Vec<usize>)>,
    next_page: usize, next_snapshot: usize,
}
impl Solution {
    pub fn new() -> Self { Self { next_page: 1, next_snapshot: 1, ..Self::default() } }
    fn live(&self) -> BTreeSet<usize> {
        let mut live: BTreeSet<_> = self.pages.iter().copied().collect();
        for (_, pages) in self.snapshots.values() { live.extend(pages); }
        live
    }
    pub fn call(&mut self, r: Value) -> Value {
        let cut = r.get("cut").map(|x| x.as_u64().unwrap() as usize);
        let sid = r.get("snapshot").map(|x| x.as_u64().unwrap() as usize);
        match r["op"].as_str().unwrap() {
            "init" => { *self=Self::new(); self.capacity=r["capacity"].as_u64().unwrap() as usize; json!({"ok":true}) },
            "crash" => json!({"ok":true}),
            "status" => json!({"used":self.allocated.len(),"live":self.live().len(),"snapshots":self.snapshots.len()}),
            "read" => match sid {
                None => json!({"data":self.data}),
                Some(id) => match self.snapshots.get(&id) { Some((data,_)) => json!({"data":data}), None => json!({"error":"snapshot"}) }
            },
            "snapshot" => { let id=self.next_snapshot; self.next_snapshot+=1;
                self.snapshots.insert(id,(self.data.clone(),self.pages.clone())); json!({"snapshot":id}) },
            "drop" => if self.snapshots.remove(&sid.unwrap()).is_some() { json!({"ok":true}) } else { json!({"error":"snapshot"}) },
            "reclaim" => { let live=self.live(); let dead:Vec<_>=self.allocated.difference(&live).copied().collect();
                let count=cut.unwrap_or(dead.len()).min(dead.len());
                for page in dead.iter().take(count) { self.allocated.remove(page); }
                if cut.is_some() {json!({"crashed":true})} else {json!({"reclaimed":count})}
            },
            "commit" => { let mut data=self.data.clone();
                for change in r["changes"].as_array().unwrap() { let key=change[0].as_str().unwrap();
                    if change[1].is_null() {data.remove(key);} else {data.insert(key.to_owned(),change[1].as_str().unwrap().to_owned());}
                }
                let n=data.len().max(1);
                if self.allocated.len()+n>self.capacity {return json!({"error":"full"});}
                let steps=cut.unwrap_or(n+1); let mut fresh=Vec::new();
                for _ in 0..steps.min(n) {fresh.push(self.next_page);self.allocated.insert(self.next_page);self.next_page+=1;}
                if steps>n {self.data=data;self.pages=fresh;}
                if cut.is_some() {json!({"crashed":true})} else {json!({"ok":true})}
            },
            _ => unreachable!(),
        }
    }
}
