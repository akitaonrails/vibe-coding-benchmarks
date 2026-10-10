use serde_json::{Value,json};
#[derive(Clone)]
pub struct Record {pub tenant:String,pub id:String,pub state:String,pub generation:u64,pub payload:Option<Value>,pub reason:Option<String>}
impl Record {
 pub fn view(&self,v:u64)->Value {
  let mut out=if v==2 {json!({"tenant":self.tenant,"id":self.id,"state":self.state,"generation":self.generation})} else {json!({"id":self.id,"status":match self.state.as_str(){"pending"=>"pending","ready"=>"ok",_=>"error"}})};
  if let Some(p)=&self.payload {out[if v==2 {"payload"} else {"value"}]=p.clone();}
  if v==2 {if let Some(r)=&self.reason {out["reason"]=json!(r);}}
  out
 }
 pub fn decode(s:&Value,tenant:&str)->Self {
  let modern=s["schema"]==2;
  let state=if modern {s["state"].as_str().unwrap()} else {match s["status"].as_str().unwrap(){"pending"=>"pending","ok"=>"ready",_=>"failed"}};
  Self{tenant:if modern{s["tenant"].as_str().unwrap()}else{tenant}.into(),id:s["id"].as_str().unwrap().into(),state:state.into(),generation:if modern{s["generation"].as_u64().unwrap()}else{1},payload:s.get(if modern{"payload"}else{"value"}).cloned(),reason:if modern{s.get("reason").map(|x|x.as_str().unwrap().into())}else if state=="failed"{Some("legacy_error".into())}else{None}}
 }
}
