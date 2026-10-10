use serde_json::{Value,json};
#[derive(Clone)]
pub struct Record {pub id:String,pub state:String,pub generation:u64,pub payload:Option<Value>,pub reason:Option<String>}
impl Record {
 pub fn view(&self)->Value {
  let mut out=json!({"id":self.id,"status":match self.state.as_str(){"pending"=>"pending","ready"=>"ok",_=>"error"}});
  if let Some(p)=&self.payload {out["value"]=p.clone();}
  out
 }
 pub fn decode(s:&Value)->Self {
  let state=match s["status"].as_str().unwrap(){"pending"=>"pending","ok"=>"ready",_=>"failed"};
  Self{id:s["id"].as_str().unwrap().into(),state:state.into(),generation:1,payload:s.get("value").cloned(),reason:if state=="failed"{Some("legacy_error".into())}else{None}}
 }
}
