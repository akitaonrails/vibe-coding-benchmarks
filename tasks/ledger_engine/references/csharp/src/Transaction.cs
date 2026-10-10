using System.Text.Json.Nodes;
namespace Ledger;
sealed class Transaction(string tenant,int revision,Table table)
{
    public string Tenant { get; } = tenant;
    public int Revision { get; } = revision;
    readonly Table snapshot = table.Clone();
    public Dictionary<string,Row?> Writes { get; } = new();
    readonly HashSet<string> points = new();
    readonly Dictionary<(string,string),Dictionary<string,int>> intervals = new();
    readonly Dictionary<string,Dictionary<string,int>> aliases = new();
    public Row? Read(string id) { points.Add(id); return Json.Copy(Writes.TryGetValue(id,out var row)?row:snapshot.Row(Tenant,id)); }
    public Table Overlay(Table? basis=null,int? revision=null)
    {
        var result=(basis??snapshot).Clone(); foreach(var (id,row) in Writes) result.Write(Tenant,id,row,revision??Revision); return result;
    }
    public IEnumerable<Row> Scan(string lo,string hi)
    {
        if(StringComparer.Ordinal.Compare(lo,hi)>=0) return [];
        intervals[(lo,hi)]=snapshot.Interval(Tenant,lo,hi);
        return Overlay().Live(Tenant).Where(r=>StringComparer.Ordinal.Compare(lo,r.Id)<=0&&StringComparer.Ordinal.Compare(r.Id,hi)<0);
    }
    public IEnumerable<Row> Lookup(string alias)
    {
        aliases[alias]=snapshot.AliasVersions(Tenant,alias); return Overlay().Live(Tenant).Where(r=>Json.Alias(r)==alias);
    }
    static bool Equal(Dictionary<string,int> a,Dictionary<string,int> b) => a.Count==b.Count&&a.All(p=>b.TryGetValue(p.Key,out var v)&&v==p.Value);
    public bool Valid(Table current) => points.Union(Writes.Keys).All(id=>snapshot.Version(Tenant,id)==current.Version(Tenant,id))
        && intervals.All(p=>Equal(p.Value,current.Interval(Tenant,p.Key.Item1,p.Key.Item2)))
        && aliases.All(p=>Equal(p.Value,current.AliasVersions(Tenant,p.Key)));
    public List<Frame> Frames(string request,int revision)
    {
        var frames=new List<Frame>{new BeginFrame(Tenant,request,revision,Writes.Count)};
        frames.AddRange(Writes.OrderBy(p=>p.Key,StringComparer.Ordinal).Select(p=>(Frame)new EditFrame(p.Key,p.Value)));
        frames.Add(new SealFrame(revision)); return frames;
    }
}
