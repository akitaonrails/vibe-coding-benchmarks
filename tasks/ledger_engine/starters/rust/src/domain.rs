use serde_json::{json, Map, Value};
use std::collections::BTreeMap;

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct Key {
    pub tenant: String,
    pub id: String,
}
impl Key {
    pub fn new(tenant: &str, id: &str) -> Self {
        Self {
            tenant: tenant.into(),
            id: id.into(),
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct Row {
    pub key: Key,
    pub value: i64,
    pub alias: Option<Value>,
    pub note: Option<Value>,
}
impl Row {
    pub fn from_request(tenant: &str, request: &Value) -> Self {
        Self {
            key: Key::new(tenant, text(request, "id")),
            value: request["value"].as_i64().unwrap(),
            alias: request.get("alias").cloned(),
            note: request.get("note").cloned(),
        }
    }
    pub fn alias(&self) -> Option<&str> {
        self.alias.as_ref().and_then(Value::as_str)
    }
    pub fn view(&self, version: u64) -> Value {
        let mut fields = Map::new();
        fields.insert("id".into(), json!(self.key.id));
        fields.insert("value".into(), json!(self.value));
        if version == 2 {
            fields.insert("tenant".into(), json!(self.key.tenant));
        }
        if let Some(alias) = &self.alias {
            fields.insert("alias".into(), alias.clone());
        }
        if let Some(note) = &self.note {
            fields.insert("note".into(), note.clone());
        }
        Value::Object(fields)
    }
}

#[derive(Clone, Debug)]
pub struct Entry {
    pub version: u64,
    pub row: Option<Row>,
}
#[derive(Clone, Debug, Default)]
pub struct State {
    pub revision: u64,
    pub entries: BTreeMap<Key, Entry>,
    pub receipts: BTreeMap<Key, u64>,
}
impl State {
    pub fn tenant_snapshot(&self, tenant: &str) -> BTreeMap<String, Entry> {
        self.entries
            .iter()
            .filter(|(key, _)| key.tenant == tenant)
            .map(|(key, entry)| (key.id.clone(), entry.clone()))
            .collect()
    }
    pub fn apply(
        &mut self,
        tenant: &str,
        request: &str,
        revision: u64,
        changes: &BTreeMap<String, Option<Row>>,
    ) {
        for (id, row) in changes {
            self.entries.insert(
                Key::new(tenant, id),
                Entry {
                    version: revision,
                    row: row.clone(),
                },
            );
        }
        self.revision = revision;
        self.receipts.insert(Key::new(tenant, request), revision);
    }
    pub fn image(&self) -> Value {
        let entries: Vec<Value> = self
            .entries
            .iter()
            .map(|(key, entry)| {
                json!({
                    "tenant": key.tenant, "id": key.id, "version": entry.version,
                    "row": entry.row.as_ref().map(|row| row.view(2))
                })
            })
            .collect();
        let receipts: Vec<Value> = self
            .receipts
            .iter()
            .map(|(key, revision)| {
                json!({
                    "tenant": key.tenant, "request": key.id, "revision": revision
                })
            })
            .collect();
        json!({"schema":2,"revision":self.revision,"entries":entries,"receipts":receipts})
    }
    pub fn from_image(image: &Value, legacy_owner: Option<&str>) -> Self {
        let mut state = Self {
            revision: number(image, "revision"),
            ..Self::default()
        };
        let legacy = number(image, "schema") == 1;
        for value in image["entries"].as_array().unwrap() {
            let tenant = if legacy {
                legacy_owner.unwrap()
            } else {
                text(value, "tenant")
            };
            let key = Key::new(tenant, text(value, "id"));
            let row = if value["row"].is_null() {
                None
            } else {
                Some(Row::from_request(tenant, &value["row"]))
            };
            state.entries.insert(
                key,
                Entry {
                    version: number(value, "version"),
                    row,
                },
            );
        }
        for value in image["receipts"].as_array().unwrap() {
            let tenant = if legacy {
                legacy_owner.unwrap()
            } else {
                text(value, "tenant")
            };
            state.receipts.insert(
                Key::new(tenant, text(value, "request")),
                number(value, "revision"),
            );
        }
        state
    }
}
pub fn text<'a>(value: &'a Value, key: &str) -> &'a str {
    value[key].as_str().unwrap()
}
pub fn number(value: &Value, key: &str) -> u64 {
    value[key].as_u64().unwrap()
}
pub fn error(code: &str) -> Value {
    json!({"error":code})
}
