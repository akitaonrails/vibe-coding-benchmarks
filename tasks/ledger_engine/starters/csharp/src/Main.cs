using System.Text.Json.Nodes;
using Ledger;
var engine = new Engine();
while (Console.ReadLine() is string line)
    Console.WriteLine(engine.Call(JsonNode.Parse(line)!.AsObject()).ToJsonString());
