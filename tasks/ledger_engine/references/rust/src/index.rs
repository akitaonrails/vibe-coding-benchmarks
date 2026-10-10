use crate::domain::{Entry, Row};
use std::collections::{BTreeMap, BTreeSet};

pub fn matching_versions(entries: &BTreeMap<String, Entry>, alias: &str) -> BTreeMap<String, u64> {
    entries
        .iter()
        .filter_map(|(id, entry)| {
            entry
                .row
                .as_ref()
                .filter(|row| row.alias() == Some(alias))
                .map(|_| (id.clone(), entry.version))
        })
        .collect()
}

pub fn unique(rows: &BTreeMap<String, Row>) -> bool {
    let mut aliases = BTreeSet::new();
    rows.values()
        .filter_map(Row::alias)
        .all(|alias| aliases.insert(alias))
}

pub fn lookup(rows: &BTreeMap<String, Row>, alias: &str) -> Vec<Row> {
    rows.values()
        .filter(|row| row.alias() == Some(alias))
        .cloned()
        .collect()
}
