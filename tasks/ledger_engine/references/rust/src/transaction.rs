use crate::domain::{Entry, Row, State};
use crate::index;
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone)]
pub struct Transaction {
    pub owner: String,
    snapshot: BTreeMap<String, Entry>,
    pub changes: BTreeMap<String, Option<Row>>,
    points: BTreeSet<String>,
    ranges: BTreeSet<(String, String)>,
    aliases: BTreeSet<String>,
}
impl Transaction {
    pub fn begin(owner: &str, state: &State) -> Self {
        Self {
            owner: owner.into(),
            snapshot: state.tenant_snapshot(owner),
            changes: BTreeMap::new(),
            points: BTreeSet::new(),
            ranges: BTreeSet::new(),
            aliases: BTreeSet::new(),
        }
    }
    pub fn overlay(&self) -> BTreeMap<String, Row> {
        let mut rows: BTreeMap<String, Row> = self
            .snapshot
            .iter()
            .filter_map(|(id, entry)| entry.row.clone().map(|row| (id.clone(), row)))
            .collect();
        Self::overlay_changes(&mut rows, &self.changes);
        rows
    }
    fn overlay_changes(rows: &mut BTreeMap<String, Row>, changes: &BTreeMap<String, Option<Row>>) {
        for (id, row) in changes {
            match row {
                Some(row) => {
                    rows.insert(id.clone(), row.clone());
                }
                None => {
                    rows.remove(id);
                }
            }
        }
    }
    pub fn read(&mut self, id: &str) -> Option<Row> {
        self.points.insert(id.into());
        self.changes
            .get(id)
            .cloned()
            .unwrap_or_else(|| self.snapshot.get(id).and_then(|entry| entry.row.clone()))
    }
    pub fn scan(&mut self, lo: &str, hi: &str) -> Vec<Row> {
        if lo >= hi {
            return Vec::new();
        }
        self.ranges.insert((lo.into(), hi.into()));
        self.overlay()
            .into_iter()
            .filter(|(id, _)| id.as_str() >= lo && id.as_str() < hi)
            .map(|(_, row)| row)
            .collect()
    }
    pub fn lookup(&mut self, alias: &str) -> Vec<Row> {
        self.aliases.insert(alias.into());
        index::lookup(&self.overlay(), alias)
    }
    fn range_versions(
        entries: &BTreeMap<String, Entry>,
        lo: &str,
        hi: &str,
    ) -> BTreeMap<String, u64> {
        entries
            .iter()
            .filter(|(id, _)| id.as_str() >= lo && id.as_str() < hi)
            .map(|(id, entry)| (id.clone(), entry.version))
            .collect()
    }
    pub fn validates(&self, current: &State) -> bool {
        for id in self.points.iter().chain(self.changes.keys()) {
            let observed = self.snapshot.get(id).map_or(0, |entry| entry.version);
            if observed != current.version(&self.owner, id) {
                return false;
            }
        }
        let entries = current.tenant_snapshot(&self.owner);
        for (lo, hi) in &self.ranges {
            if Self::range_versions(&self.snapshot, lo, hi)
                != Self::range_versions(&entries, lo, hi)
            {
                return false;
            }
        }
        self.aliases.iter().all(|alias| {
            index::matching_versions(&self.snapshot, alias)
                == index::matching_versions(&entries, alias)
        })
    }
    pub fn proposed_unique(&self, current: &State) -> bool {
        let mut rows = current
            .tenant_snapshot(&self.owner)
            .into_iter()
            .filter_map(|(id, entry)| entry.row.map(|row| (id, row)))
            .collect();
        Self::overlay_changes(&mut rows, &self.changes);
        index::unique(&rows)
    }
}
