use crate::domain::{number, text, Row, State};
use serde_json::{json, Value};
use std::collections::BTreeMap;

#[derive(Clone)]
enum Frame {
    Begin {
        tenant: String,
        request: String,
        revision: u64,
        count: usize,
    },
    Edit {
        id: String,
        row: Option<Row>,
    },
    Seal {
        revision: u64,
    },
}
impl Frame {
    fn view(&self) -> Value {
        match self {
            Self::Begin {
                tenant,
                request,
                revision,
                count,
            } => {
                json!({"kind":"BEGIN","tenant":tenant,"request":request,"revision":revision,"count":count})
            }
            Self::Edit { id, row } => {
                json!({"kind":"EDIT","id":id,"row":row.as_ref().map(|r| r.view(2))})
            }
            Self::Seal { revision } => json!({"kind":"SEAL","revision":revision}),
        }
    }
}

pub struct Device {
    checkpoint: Value,
    legacy_owner: Option<String>,
    journal: Vec<Frame>,
    loaded: bool,
    pub capacity: usize,
}
impl Default for Device {
    fn default() -> Self {
        Self {
            checkpoint: State::default().image(),
            legacy_owner: None,
            journal: Vec::new(),
            loaded: false,
            capacity: 64,
        }
    }
}
impl Device {
    pub fn with_capacity(capacity: usize) -> Self {
        Self {
            capacity,
            ..Self::default()
        }
    }
    pub fn frames(&self) -> usize {
        self.journal.len()
    }
    pub fn can_append(&self, changes: usize) -> bool {
        self.frames() + changes + 2 <= self.capacity
    }
    pub fn pristine(&self) -> bool {
        !self.loaded
            && number(&self.checkpoint, "revision") == 0
            && self.journal.is_empty()
            && self.checkpoint["entries"].as_array().unwrap().is_empty()
            && self.checkpoint["receipts"].as_array().unwrap().is_empty()
    }
    pub fn load(&mut self, image: &Value, owner: &str) -> State {
        self.checkpoint = image.clone();
        self.legacy_owner = Some(owner.into());
        self.loaded = true;
        self.recover()
    }
    pub fn append(
        &mut self,
        tenant: &str,
        request: &str,
        revision: u64,
        changes: &BTreeMap<String, Option<Row>>,
    ) {
        let mut proposed = vec![Frame::Begin {
            tenant: tenant.into(),
            request: request.into(),
            revision,
            count: changes.len(),
        }];
        proposed.extend(changes.iter().map(|(id, row)| Frame::Edit {
            id: id.clone(),
            row: row.clone(),
        }));
        proposed.push(Frame::Seal { revision });
        self.journal.extend(proposed);
    }
    pub fn checkpoint(&mut self, state: &State) {
        self.checkpoint = state.image();
        self.legacy_owner = None;
        self.journal.clear();
    }
    pub fn recover(&mut self) -> State {
        let mut state = State::from_image(&self.checkpoint, self.legacy_owner.as_deref());
        let mut cursor = 0;
        while cursor < self.journal.len() {
            let (tenant, request, revision, count) = match &self.journal[cursor] {
                Frame::Begin {
                    tenant,
                    request,
                    revision,
                    count,
                } => (tenant, request, *revision, *count),
                _ => break,
            };
            let seal_index = cursor + count + 1;
            if seal_index >= self.journal.len() {
                break;
            }
            if !matches!(self.journal[seal_index], Frame::Seal { revision: r } if r == revision) {
                break;
            }
            let mut changes = BTreeMap::new();
            let mut valid = true;
            for frame in &self.journal[cursor + 1..seal_index] {
                match frame {
                    Frame::Edit { id, row } => {
                        changes.insert(id.clone(), row.clone());
                    }
                    _ => {
                        valid = false;
                        break;
                    }
                }
            }
            if !valid || changes.len() != count {
                break;
            }
            state.apply(tenant, request, revision, &changes);
            cursor = seal_index + 1;
        }
        self.journal.truncate(cursor);
        state
    }
    pub fn inspect(&self, tenant: &str) -> Value {
        let mut image = self.checkpoint.clone();
        let legacy = number(&image, "schema") == 1;
        for field in ["entries", "receipts"] {
            image[field].as_array_mut().unwrap().retain(|value| {
                if legacy {
                    self.legacy_owner.as_deref() == Some(tenant)
                } else {
                    text(value, "tenant") == tenant
                }
            });
        }
        let mut journal = Vec::new();
        let mut include = false;
        for frame in &self.journal {
            if let Frame::Begin { tenant: owner, .. } = frame {
                include = owner == tenant;
            }
            if include {
                journal.push(frame.view());
            }
        }
        json!({"checkpoint":image,"journal":journal})
    }
}
