use crate::domain::Row;
use std::collections::BTreeMap;

pub fn lookup(rows: &BTreeMap<String, Row>, alias: &str) -> Vec<Row> {
    rows.values()
        .filter(|row| row.alias() == Some(alias))
        .cloned()
        .collect()
}
