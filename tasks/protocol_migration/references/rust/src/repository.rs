use std::collections::HashMap;
use crate::domain::Record;
pub type Key=(String,String);
#[derive(Default)]
pub struct Repository {rows:HashMap<Key,Record>,cache:HashMap<Key,Option<Record>>}
impl Repository {
 pub fn read(&mut self,key:&Key)->Option<Record>{self.cache.entry(key.clone()).or_insert_with(||self.rows.get(key).cloned()).clone()}
 pub fn write(&mut self,key:Key,record:Record){self.cache.remove(&key);self.rows.insert(key,record);}
}
