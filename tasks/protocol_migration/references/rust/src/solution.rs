use serde_json::{Value,json};
use crate::{domain::Record,repository::Repository,worker};
#[derive(Default)]
pub struct Solution {repository:Repository}
impl Solution {
 pub fn call(&mut self,q:Value)->Value {
  let v=q.get("v").and_then(Value::as_u64).unwrap_or(1);
  
  let tenant=if v==1{"legacy"}else{q["tenant"].as_str().unwrap()};
  if v==2 && q["actor"].as_str()!=Some(tenant){return json!({"error":"forbidden"})}
  let id=q["id"].as_str().unwrap();let key=(tenant.to_string(),id.to_string());
  let old=self.repository.read(&key);let op=q["op"].as_str().unwrap();
  if op=="get" || op=="export" {
   return match old {None=>json!({"error":"not_found"}),Some(r)=>{let mut view=r.view(v);if op=="export" {view["schema"]=json!(v);json!({"stored":view})}else{json!({"record":view})}}};
  }
  let record=match op {
   "submit"=>{if old.is_some(){return json!({"error":"conflict"})} Record{tenant:tenant.into(),id:id.into(),state:"pending".into(),generation:1,payload:q.get("payload").cloned(),reason:None}},
   "import"=>{let s=&q["stored"];
    if s["id"]!=q["id"] || (s["schema"]==2 && s["tenant"]!=tenant){return json!({"error":"identity"})} Record::decode(s,tenant)},
   _=>{let Some(mut r)=old else{return json!({"error":"not_found"})};if let Err(e)=worker::apply(&mut r,&q,v){return json!({"error":e})}r}
  };
  let view=record.view(v);self.repository.write(key,record);json!({"record":view})
 }
}
