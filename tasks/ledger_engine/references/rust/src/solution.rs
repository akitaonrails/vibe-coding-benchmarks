use crate::device::{Device, Fault};
use crate::domain::{error, number, text, Key, Row, State};
use crate::transaction::Transaction;
use serde_json::{json, Value};
use std::collections::BTreeMap;

#[derive(Default)]
pub struct Solution {
    state: State,
    device: Device,
    transactions: BTreeMap<String, Transaction>,
}
impl Solution {
    fn recover(&mut self) {
        self.state = self.device.recover();
        self.transactions.clear();
    }
    fn owner(&self, request: &Value) -> Result<String, &'static str> {
        if request.get("v").and_then(Value::as_u64).unwrap_or(1) == 1 {
            return Ok("legacy".into());
        }
        let tenant = text(request, "tenant");
        if text(request, "actor") != tenant {
            return Err("forbidden");
        }
        Ok(tenant.into())
    }
    fn handle(&self, request: &Value, owner: &str) -> Result<String, &'static str> {
        let handle = request
            .get("tx")
            .and_then(Value::as_str)
            .ok_or("transaction_missing")?;
        let transaction = self.transactions.get(handle).ok_or("transaction_missing")?;
        if transaction.owner != owner {
            return Err("transaction_owner");
        }
        Ok(handle.into())
    }
    fn commit(&mut self, request: &Value, owner: &str) -> Value {
        let commit_id = text(request, "request");
        if let Some(revision) = self.state.receipts.get(&Key::new(owner, commit_id)) {
            return json!({"committed":revision});
        }
        let handle = match self.handle(request, owner) {
            Ok(handle) => handle,
            Err(code) => return error(code),
        };
        let transaction = &self.transactions[&handle];
        if !transaction.validates(&self.state) {
            return error("conflict");
        }
        if !transaction.proposed_unique(&self.state) {
            return error("unique");
        }
        if !self.device.can_append(transaction.changes.len()) {
            return error("capacity");
        }
        let revision = self.state.revision + 1;
        let fault = request.get("fault").map(Fault::parse);
        self.device.append(
            owner,
            commit_id,
            revision,
            &transaction.changes,
            fault.as_ref(),
        );
        if fault.is_some() {
            self.recover();
            return error("interrupted");
        }
        self.state
            .apply(owner, commit_id, revision, &transaction.changes);
        self.transactions.remove(&handle);
        json!({"committed":revision})
    }
    pub fn call(&mut self, request: Value) -> Value {
        let operation = text(&request, "op");
        match operation {
            "init" => {
                self.state = State::default();
                self.device = Device::with_capacity(number(&request, "capacity") as usize);
                self.transactions.clear();
                return json!({"ok":true});
            }
            "stats" => {
                return json!({"revision":self.state.revision,"journal_frames":self.device.frames(),
                                     "capacity":self.device.capacity,"transactions":self.transactions.len()})
            }
            "crash" => {
                self.recover();
                return json!({"recovered":self.state.revision});
            }
            "checkpoint" => {
                let fault = request.get("fault").map(Fault::parse);
                self.device.checkpoint(&self.state, fault.as_ref());
                if fault.is_some() {
                    self.recover();
                    return error("interrupted");
                }
                return json!({"checkpoint":self.state.revision});
            }
            _ => {}
        }
        let owner = match self.owner(&request) {
            Ok(owner) => owner,
            Err(code) => return error(code),
        };
        let version = request.get("v").and_then(Value::as_u64).unwrap_or(1);
        match operation {
            "inspect" => return self.device.inspect(&owner),
            "load" => {
                if self.state.revision != 0
                    || !self.transactions.is_empty()
                    || !self.device.pristine()
                {
                    return error("not_empty");
                }
                self.state = self.device.load(&request["image"], &owner);
                return json!({"loaded":self.state.revision});
            }
            "begin" => {
                let handle = text(&request, "tx");
                if self.transactions.contains_key(handle) {
                    return error("transaction_exists");
                }
                self.transactions
                    .insert(handle.into(), Transaction::begin(&owner, &self.state));
                return json!({"snapshot":self.state.revision});
            }
            "commit" => return self.commit(&request, &owner),
            _ => {}
        }
        let handle = match self.handle(&request, &owner) {
            Ok(handle) => handle,
            Err(code) => return error(code),
        };
        if operation == "abort" {
            self.transactions.remove(&handle);
            return json!({"ok":true});
        }
        let transaction = self.transactions.get_mut(&handle).unwrap();
        match operation {
            "read" => {
                json!({"record":transaction.read(text(&request, "id")).map(|row| row.view(version))})
            }
            "scan" => {
                let rows: Vec<Value> = transaction
                    .scan(text(&request, "lo"), text(&request, "hi"))
                    .iter()
                    .map(|row| row.view(version))
                    .collect();
                json!({"records":rows})
            }
            "lookup" => {
                let rows: Vec<Value> = transaction
                    .lookup(text(&request, "alias"))
                    .iter()
                    .map(|row| row.view(version))
                    .collect();
                json!({"records":rows})
            }
            "put" => {
                let row = Row::from_request(&owner, &request);
                transaction.changes.insert(row.key.id.clone(), Some(row));
                json!({"ok":true})
            }
            "delete" => {
                transaction
                    .changes
                    .insert(text(&request, "id").into(), None);
                json!({"ok":true})
            }
            _ => unreachable!("contract operation"),
        }
    }
}
