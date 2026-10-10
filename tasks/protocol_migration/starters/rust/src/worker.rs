use serde_json::Value;
use crate::domain::Record;
pub fn apply(r:&mut Record,q:&Value)->Result<(), &'static str>{
 match q["op"].as_str().unwrap(){
 "complete"=>{
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
