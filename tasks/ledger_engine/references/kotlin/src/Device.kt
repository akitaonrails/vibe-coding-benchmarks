import com.google.gson.*
data class Recovered(val table: Table,val receipts: MutableMap<Key,Int>,val revision: Int)
class Device(val capacity: Int) {
    var image=obj("schema" to 2,"revision" to 0,"entries" to JsonArray(),"receipts" to JsonArray()); private set
    var journal=mutableListOf<Frame>(); private set
    private var legacyOwner: String?=null
    var loaded=false; private set
    fun append(frames: List<Frame>,fault: JsonObject?) {
        val kept=frames.take(fault?.number("keep") ?: frames.size).toMutableList()
        if(fault?.get("tear")?.asBoolean==true && kept.isNotEmpty()) kept[kept.lastIndex]=TornFrame
        journal.addAll(kept)
    }
    fun publish(next: JsonObject,fault: JsonObject?) {
        if(fault!=null && (fault.number("keep")!=2 || fault["tear"].asBoolean)) return
        image=next.deepCopy(); legacyOwner=null; journal.clear()
    }
    fun load(next: JsonObject,tenant: String) { image=next.deepCopy(); legacyOwner=tenant; loaded=true; journal.clear() }
    fun groups(): List<Pair<BeginFrame,List<EditFrame>>> {
        val result=mutableListOf<Pair<BeginFrame,List<EditFrame>>>(); var position=0
        while(position<journal.size) {
            val head=journal[position] as? BeginFrame ?: break
            val count=head.count; val end=position+count+1
            if(end>=journal.size) break
            val edits=journal.subList(position+1,end).toList(); val seal=journal[end]
            if(edits.any { it !is EditFrame } || seal !is SealFrame || seal.revision!=head.revision) break
            result.add(head to edits.filterIsInstance<EditFrame>()); position=end+1
        }
        journal=journal.take(position).toMutableList(); return result
    }
    fun recover(): Recovered {
        val table=Table(); val receipts=mutableMapOf<Key,Int>(); var revision=image.number("revision"); val legacy=image.number("schema")==1
        for(item in image.getAsJsonArray("entries")) {
            val e=item.asJsonObject; val tenant=if(legacy) legacyOwner!! else e.text("tenant"); val row=if(e["row"].isJsonNull) null else Row.fromJson(e["row"].asJsonObject,tenant,e.text("id"))
            table.write(tenant,e.text("id"),row,e.number("version"))
        }
        for(item in image.getAsJsonArray("receipts")) { val r=item.asJsonObject; receipts[Key(if(legacy) legacyOwner!! else r.text("tenant"),r.text("request"))]=r.number("revision") }
        for((head,edits) in groups()) {
            revision=head.revision; val tenant=head.tenant
            for(e in edits) table.write(tenant,e.id,e.row,revision)
            receipts[Key(tenant,head.request)]=revision
        }
        return Recovered(table,receipts,revision)
    }
    fun inspect(tenant: String): JsonObject {
        val filtered=image.deepCopy()
        for(field in listOf("entries","receipts")) filtered.add(field,array(image.getAsJsonArray(field).filter { if(image.number("schema")==1) legacyOwner==tenant else it.asJsonObject.text("tenant")==tenant }))
        val frames=groups().filter { it.first.tenant==tenant }.flatMap { (h,e) -> listOf(h.toJson())+e.map { it.toJson() }+SealFrame(h.revision).toJson() }
        return obj("checkpoint" to filtered,"journal" to array(frames))
    }
}
