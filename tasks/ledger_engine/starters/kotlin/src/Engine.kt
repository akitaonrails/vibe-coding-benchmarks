import com.google.gson.*
class Engine {
    private var device=Device(64)
    private var table=Table()
    private var receipts=mutableMapOf<Key,Int>()
    private var revision=0
    private val transactions=mutableMapOf<String,Transaction>()
    private fun recover() { val r=device.recover(); table=r.table; receipts=r.receipts; revision=r.revision; transactions.clear() }
    private fun failure(code: String)=obj("error" to code)
    private fun image()=obj("schema" to 2,"revision" to revision,"entries" to table.imageEntries(),"receipts" to array(receipts.toList().sortedWith(compareBy({it.first.tenant},{it.first.id})).map { (key,v) -> obj("tenant" to key.tenant,"request" to key.id,"revision" to v) }))
    private fun commit(request: JsonObject,tenant: String): JsonObject {
        val identity=Key(tenant,request.text("request"))
        val tx=transactions[request["tx"]?.asString] ?: return failure("transaction_missing")
        if(tx.tenant!=tenant) return failure("transaction_owner")
        if(request.has("fault")) return failure("unsupported_fault")
        val next=revision+1; val proposed=tx.overlay(table,next)
        val frames=tx.frames(request.text("request"),next)
        if(device.journal.size+frames.size>device.capacity) return failure("capacity")
        device.append(frames,null)
        table=proposed; revision=next; receipts[identity]=revision; transactions.remove(request.text("tx"))
        return obj("committed" to revision)
    }
    fun call(request: JsonObject): JsonObject {
        val op=request.text("op")
        when(op) {
            "init" -> { device=Device(request.number("capacity")); recover(); return obj("ok" to true) }
            "stats" -> return obj("revision" to revision,"journal_frames" to device.journal.size,"capacity" to device.capacity,"transactions" to transactions.size)
            "crash" -> { recover(); return obj("recovered" to revision) }
            "checkpoint" -> { if(request.has("fault")) return failure("unsupported_fault"); device.publish(image(),null); return obj("checkpoint" to revision) }
        }
        val version=request["v"]?.asInt ?: 1
        if(version!=1) return failure("unsupported_version")
        val tenant="legacy"
        when(op) {
            "inspect" -> return device.inspect(tenant)
            "load" -> {
                if(revision!=0 || transactions.isNotEmpty() || device.journal.isNotEmpty() || device.loaded || device.image.getAsJsonArray("entries").size()!=0 || device.image.getAsJsonArray("receipts").size()!=0) return failure("not_empty")
                device.load(request.getAsJsonObject("image"),tenant); recover(); return obj("loaded" to revision)
            }
            "begin" -> { if(transactions.containsKey(request.text("tx"))) return failure("transaction_exists"); transactions[request.text("tx")]=Transaction(tenant,revision,table); return obj("snapshot" to revision) }
            "commit" -> return commit(request,tenant)
        }
        val tx=transactions[request.text("tx")] ?: return failure("transaction_missing")
        if(tx.tenant!=tenant) return failure("transaction_owner")
        when(op) {
            "read" -> return obj("record" to wire(tx.read(request.text("id")),version))
            "scan" -> return obj("records" to array(tx.scan(request.text("lo"),request.text("hi")).map { wire(it,version) }))
            "lookup" -> return obj("records" to array(tx.lookup(request.text("alias")).map { wire(it,version) }))
            "put" -> tx.writes[request.text("id")]=record(tenant,request.text("id"),request)
            "delete" -> tx.writes[request.text("id")]=null
            "abort" -> transactions.remove(request.text("tx"))
        }
        return obj("ok" to true)
    }
}
