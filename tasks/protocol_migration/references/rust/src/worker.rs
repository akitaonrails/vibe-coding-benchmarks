use serde_json::Value;
use crate::domain::Record;
pub fn apply(r:&mut Record,q:&Value,v:u64)->Result<(), &'static str>{
 match q["op"].as_str().unwrap(){
 "complete"=>{
  if v==2 && q["generation"].as_u64()!=Some(r.generation){return Err("stale")}
  if r.state!="pending" {return Err("conflict")}
  r.payload=None;
  if let Some(reason)=q.get("reason"){r.state="failed".into();r.reason=Some(reason.as_str().unwrap().into());}
  else {r.state="ready".into();r.payload=q.get("payload").cloned();}
 },
 "cancel"=>{if r.state=="cancelled" {return Ok(())} if r.state!="pending" && r.state!="cancelled" {return Err("conflict")} r.state="cancelled".into();r.payload=None;},
 "retry"=>{if r.state!="failed" && r.state!="cancelled" {return Err("conflict")} r.state="pending".into();r.generation+=1;r.payload=None;r.reason=None;},
 _=>unreachable!()
 }
 Ok(())
}
