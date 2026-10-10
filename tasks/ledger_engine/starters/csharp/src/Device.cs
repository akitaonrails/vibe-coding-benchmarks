using System.Text.Json.Nodes;
namespace Ledger;
sealed class Device(int capacity)
{
    public int Capacity { get; } = capacity;
    public JsonObject Image { get; private set; } = Json.Obj(("schema",2),("revision",0),("entries",new JsonArray()),("receipts",new JsonArray()));
    public List<Frame> Journal { get; private set; } = new();
    public string? LegacyOwner { get; private set; }
    public bool Loaded { get; private set; }
    public void Append(List<Frame> frames,JsonNode? fault)
    {
        Journal.AddRange(frames);
    }
    public void Publish(JsonObject image,JsonNode? fault)
    {
        Image=(JsonObject)image.DeepClone(); LegacyOwner=null; Journal.Clear();
    }
    public void Load(JsonObject image,string tenant) { Image=(JsonObject)image.DeepClone(); LegacyOwner=tenant; Loaded=true; Journal.Clear(); }
    public List<(BeginFrame Header,List<EditFrame> Edits)> Groups()
    {
        var groups=new List<(BeginFrame,List<EditFrame>)>(); int pos=0;
        while(pos<Journal.Count)
        {
            if(Journal[pos] is not BeginFrame head) break;
            int end=pos+head.Count+1;
            if(end>=Journal.Count) break;
            var segment=Journal.Skip(pos+1).Take(head.Count).ToList();
            if(segment.Any(e=>e is not EditFrame)||Journal[end] is not SealFrame seal||seal.Revision!=head.Revision) break;
            groups.Add((head,segment.Cast<EditFrame>().ToList())); pos=end+1;
        }
        Journal=Journal.Take(pos).ToList(); return groups;
    }
    public (Table,Dictionary<Key,int>,int) Recover()
    {
        var table=new Table(); var receipts=new Dictionary<Key,int>(); int revision=Image.Number("revision"); bool legacy=Image.Number("schema")==1;
        foreach(var e in Image["entries"]!.AsArray())
        {
            string tenant=legacy?LegacyOwner!:e!.Text("tenant"); var row=e!["row"] is JsonObject raw?Row.FromJson(raw,tenant,e.Text("id")):null;
            table.Write(tenant,e.Text("id"),row,e.Number("version"));
        }
        foreach(var r in Image["receipts"]!.AsArray()) receipts[new(legacy?LegacyOwner!:r!.Text("tenant"),r!.Text("request"))]=r!.Number("revision");
        foreach(var (header,edits) in Groups())
        {
            revision=header.Revision; string tenant=header.Tenant;
            foreach(var e in edits) table.Write(tenant,e.Id,e.Row,revision);
            receipts[new(tenant,header.Request)]=revision;
        }
        return(table,receipts,revision);
    }
    public JsonObject Inspect(string tenant)
    {
        var image=(JsonObject)Image.DeepClone();
        foreach(var name in new[]{"entries","receipts"})
            image[name]=Json.Array(Image[name]!.AsArray().Where(e=>Image.Number("schema")==1?LegacyOwner==tenant:e!.Text("tenant")==tenant));
        var frames=new List<JsonNode?>();
        foreach(var (h,edits) in Groups()) if(h.Tenant==tenant) { frames.Add(h.ToJson()); frames.AddRange(edits.Select(e=>e.ToJson())); frames.Add(new SealFrame(h.Revision).ToJson()); }
        return Json.Obj(("checkpoint",image),("journal",Json.Array(frames)));
    }
}
