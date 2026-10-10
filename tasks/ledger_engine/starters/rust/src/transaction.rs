use crate::domain::{Entry, Row, State};
use crate::index;
use std::collections::BTreeMap;

pub struct Transaction {
    pub owner: String,
    snapshot: BTreeMap<String, Entry>,
    pub changes: BTreeMap<String, Option<Row>>,
}
impl Transaction {
    pub fn begin(owner: &str, state: &State) -> Self {
        Self {
            owner: owner.into(),
            snapshot: state.tenant_snapshot(owner),
            changes: BTreeMap::new(),
        }
    }
    pub fn overlay(&self) -> BTreeMap<String, Row> {
        let mut rows: BTreeMap<String, Row> = self
            .snapshot
            .iter()
            .filter_map(|(id, entry)| entry.row.clone().map(|row| (id.clone(), row)))
            .collect();
        for (id, row) in &self.changes {
            match row {
                Some(row) => {
                    rows.insert(id.clone(), row.clone());
                }
                None => {
                    rows.remove(id);
                }
            }
        }
        rows
    }
    pub fn read(&mut self, id: &str) -> Option<Row> {
        self.changes
            .get(id)
            .cloned()
            .unwrap_or_else(|| self.snapshot.get(id).and_then(|entry| entry.row.clone()))
    }
    pub fn scan(&mut self, lo: &str, hi: &str) -> Vec<Row> {
        if lo >= hi {
            return Vec::new();
        }
        self.overlay()
            .into_iter()
            .filter(|(id, _)| id.as_str() >= lo && id.as_str() < hi)
            .map(|(_, row)| row)
            .collect()
    }
    pub fn lookup(&mut self, alias: &str) -> Vec<Row> {
        index::lookup(&self.overlay(), alias)
    }
}
