using System.Text.Json.Nodes;
namespace Ledger;
readonly record struct Key(string Tenant, string Id);
sealed record Entry(int Version, Row? Row);
static class Json
{
    public static string Text(this JsonNode n, string key) => n[key]!.GetValue<string>();
    public static int Number(this JsonNode n, string key) => n[key]!.GetValue<int>();
    public static JsonObject Obj(params (string, object?)[] fields)
    {
        var o = new JsonObject();
        foreach (var (k, v) in fields) o[k] = v switch {
            null => null, Row row => row.ToJson(), Frame frame => frame.ToJson(), JsonNode node => node.DeepClone(), string s => JsonValue.Create(s),
            int i => JsonValue.Create(i), bool b => JsonValue.Create(b), _ => throw new ArgumentException() };
        return o;
    }
    public static JsonArray Array(IEnumerable<JsonNode?> values) => new(values.Select(x => x?.DeepClone()).ToArray());
    public static Row? Copy(Row? row) => row is null ? null : row with { Note = new(row.Note.Present,row.Note.Value?.DeepClone()) };
    public static string? Alias(Row? row) => row?.Alias.Value;
    public static Row Record(string tenant, string identifier, JsonObject request) => Row.FromJson(request,tenant,identifier);
    public static JsonObject? Wire(Row? row,int version)
    {
        var result=row?.ToJson(); if(version==1) result?.Remove("tenant"); return result;
    }
}
readonly record struct Presence<T>(bool Present,T Value);
sealed record Row(string Tenant,string Id,int Value,Presence<string?> Alias,Presence<JsonNode?> Note)
{
    public static Row FromJson(JsonObject input,string? tenant=null,string? id=null) => new(
        tenant??input.Text("tenant"),id??input.Text("id"),input.Number("value"),
        new(input.ContainsKey("alias"),input["alias"]?.GetValue<string>()),
        new(input.ContainsKey("note"),input["note"]?.DeepClone()));
    public JsonObject ToJson()
    {
        var result=Json.Obj(("tenant",Tenant),("id",Id),("value",Value));
        if(Alias.Present) result["alias"]=Alias.Value;
        if(Note.Present) result["note"]=Note.Value?.DeepClone();
        return result;
    }
}
abstract record Frame
{
    public abstract JsonObject ToJson();
}
sealed record BeginFrame(string Tenant,string Request,int Revision,int Count):Frame
{
    public override JsonObject ToJson()=>Json.Obj(("kind","BEGIN"),("tenant",Tenant),("request",Request),("revision",Revision),("count",Count));
}
sealed record EditFrame(string Id,Row? Row):Frame
{
    public override JsonObject ToJson()=>Json.Obj(("kind","EDIT"),("id",Id),("row",Row));
}
sealed record SealFrame(int Revision):Frame
{
    public override JsonObject ToJson()=>Json.Obj(("kind","SEAL"),("revision",Revision));
}
sealed record TornFrame:Frame
{
    public override JsonObject ToJson()=>Json.Obj(("kind","TORN"));
}
