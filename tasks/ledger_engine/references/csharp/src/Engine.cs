using System.Text.Json.Nodes;
namespace Ledger;
sealed class Engine
{
    Device device=new(64); Table table=new(); Dictionary<Key,int> receipts=new(); int revision;
    readonly Dictionary<string,Transaction> transactions=new();
    void Recover() { (table,receipts,revision)=device.Recover(); transactions.Clear(); }
    static JsonObject Error(string code)=>Json.Obj(("error",code));
    JsonObject Image()=>Json.Obj(("schema",2),("revision",revision),("entries",table.ImageEntries()),("receipts",Json.Array(receipts.OrderBy(p=>p.Key.Tenant,StringComparer.Ordinal).ThenBy(p=>p.Key.Id,StringComparer.Ordinal).Select(p=>Json.Obj(("tenant",p.Key.Tenant),("request",p.Key.Id),("revision",p.Value))))));
    JsonObject Commit(JsonObject request,string tenant)
    {
        var identity=new Key(tenant,request.Text("request"));
        if(receipts.TryGetValue(identity,out var prior)) return Json.Obj(("committed",prior));
        if(!transactions.TryGetValue(request["tx"]?.GetValue<string>()??"",out var tx)) return Error("transaction_missing");
        if(tx.Tenant!=tenant) return Error("transaction_owner");
        if(!tx.Valid(table)) return Error("conflict");
        int next=revision+1; var proposed=tx.Overlay(table,next);
        if(!proposed.Unique()) return Error("unique");
        var frames=tx.Frames(request.Text("request"),next);
        if(device.Journal.Count+frames.Count>device.Capacity) return Error("capacity");
        device.Append(frames,request["fault"]);
        if(request.ContainsKey("fault")) { Recover(); return Error("interrupted"); }
        table=proposed; revision=next; receipts[identity]=revision; transactions.Remove(request.Text("tx"));
        return Json.Obj(("committed",revision));
    }
    public JsonObject Call(JsonObject request)
    {
        string op=request.Text("op");
        switch(op)
        {
            case "init": device=new(request.Number("capacity")); Recover(); return Json.Obj(("ok",true));
            case "stats": return Json.Obj(("revision",revision),("journal_frames",device.Journal.Count),("capacity",device.Capacity),("transactions",transactions.Count));
            case "crash": Recover(); return Json.Obj(("recovered",revision));
            case "checkpoint": device.Publish(Image(),request["fault"]); if(request.ContainsKey("fault")) { Recover(); return Error("interrupted"); } return Json.Obj(("checkpoint",revision));
        }
        int version=request["v"]?.GetValue<int>()??1; string tenant=version==1?"legacy":request.Text("tenant");
        if(version==2&&request.Text("actor")!=tenant) return Error("forbidden");
        switch(op)
        {
            case "inspect": return device.Inspect(tenant);
            case "load":
                if(revision!=0||transactions.Count!=0||device.Journal.Count!=0||device.Loaded||device.Image["entries"]!.AsArray().Count!=0||device.Image["receipts"]!.AsArray().Count!=0) return Error("not_empty");
                device.Load(request["image"]!.AsObject(),tenant); Recover(); return Json.Obj(("loaded",revision));
            case "begin":
                if(transactions.ContainsKey(request.Text("tx"))) return Error("transaction_exists");
                transactions[request.Text("tx")]=new(tenant,revision,table); return Json.Obj(("snapshot",revision));
            case "commit": return Commit(request,tenant);
        }
        if(!transactions.TryGetValue(request.Text("tx"),out var tx)) return Error("transaction_missing");
        if(tx.Tenant!=tenant) return Error("transaction_owner");
        switch(op)
        {
            case "read": return Json.Obj(("record",Json.Wire(tx.Read(request.Text("id")),version)));
            case "scan": return Json.Obj(("records",Json.Array(tx.Scan(request.Text("lo"),request.Text("hi")).Select(r=>Json.Wire(r,version)))));
            case "lookup": return Json.Obj(("records",Json.Array(tx.Lookup(request.Text("alias")).Select(r=>Json.Wire(r,version)))));
            case "put": tx.Writes[request.Text("id")]=Json.Record(tenant,request.Text("id"),request); break;
            case "delete": tx.Writes[request.Text("id")]=null; break;
            case "abort": transactions.Remove(request.Text("tx")); break;
        }
        return Json.Obj(("ok",true));
    }
}
