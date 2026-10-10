import com.google.gson.JsonObject
class Transaction(val tenant: String,val revision: Int,table: Table) {
    private val snapshot=table.copy()
    val writes=mutableMapOf<String,Row?>()
    private val points=mutableSetOf<String>()
    private val intervals=mutableMapOf<Pair<String,String>,Map<String,Int>>()
    private val aliases=mutableMapOf<String,Map<String,Int>>()
    fun read(id: String): Row? { points.add(id); return (if(writes.containsKey(id)) writes[id] else snapshot.row(tenant,id))?.ownedCopy() }
    fun overlay(basis: Table=snapshot,revision: Int=this.revision) = basis.copy().also { table -> writes.forEach { (id,row) -> table.write(tenant,id,row,revision) } }
    fun scan(lo: String,hi: String): List<Row> {
        if(lo>=hi) return emptyList()
        intervals[lo to hi]=snapshot.interval(tenant,lo,hi)
        return overlay().live(tenant).filter { it.id>=lo && it.id<hi }
    }
    fun lookup(name: String): List<Row> { aliases[name]=snapshot.aliasVersions(tenant,name); return overlay().live(tenant).filter { alias(it)==name } }
    fun valid(table: Table) = (points+writes.keys).all { snapshot.version(tenant,it)==table.version(tenant,it) } && intervals.all { (bounds,versions) -> versions==table.interval(tenant,bounds.first,bounds.second) } && aliases.all { (name,versions) -> versions==table.aliasVersions(tenant,name) }
    fun frames(request: String,revision: Int): List<Frame> = listOf(BeginFrame(tenant,request,revision,writes.size)) + writes.toSortedMap().map { (id,row) -> EditFrame(id,row?.ownedCopy()) } + SealFrame(revision)
}
