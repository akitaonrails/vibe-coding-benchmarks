using System.Text.Json.Nodes;
namespace Ledger;
sealed class Table
{
    public Dictionary<Key, Entry> Entries { get; } = new();
    public Table Clone()
    {
        var copy = new Table(); foreach (var (key, entry) in Entries) copy.Entries[key] = new(entry.Version, Json.Copy(entry.Row)); return copy;
    }
    public int Version(string tenant, string id) => Entries.TryGetValue(new(tenant,id), out var e) ? e.Version : 0;
    public Row? Row(string tenant, string id) => Entries.GetValueOrDefault(new(tenant,id))?.Row;
    public void Write(string tenant, string id, Row? row, int version) => Entries[new(tenant,id)] = new(version,Json.Copy(row));
    public IEnumerable<Row> Live(string tenant) => Entries.Where(p => p.Key.Tenant == tenant && p.Value.Row != null).OrderBy(p => p.Key.Id, StringComparer.Ordinal).Select(p => p.Value.Row!);
    public Dictionary<string,int> Interval(string tenant, string lo, string hi) => Entries.Where(p => p.Key.Tenant == tenant && StringComparer.Ordinal.Compare(lo,p.Key.Id)<=0 && StringComparer.Ordinal.Compare(p.Key.Id,hi)<0).ToDictionary(p => p.Key.Id,p=>p.Value.Version);
    public Dictionary<string,int> AliasVersions(string tenant,string alias) => Live(tenant).Where(r=>Json.Alias(r)==alias).ToDictionary(r=>r.Id,r=>Version(tenant,r.Id));
    public JsonArray ImageEntries() => Json.Array(Entries.OrderBy(p=>p.Key.Tenant,StringComparer.Ordinal).ThenBy(p=>p.Key.Id,StringComparer.Ordinal).Select(p=>Json.Obj(("tenant",p.Key.Tenant),("id",p.Key.Id),("version",p.Value.Version),("row",p.Value.Row))));
}
