import com.google.gson.JsonObject
class Table {
    val entries = mutableMapOf<Key,Entry>()
    fun copy() = Table().also { result -> entries.forEach { (key,e) -> result.entries[key]=Entry(e.version,e.row?.ownedCopy()) } }
    fun version(tenant: String,id: String) = entries[Key(tenant,id)]?.version ?: 0
    fun row(tenant: String,id: String) = entries[Key(tenant,id)]?.row
    fun write(tenant: String,id: String,row: Row?,revision: Int) { entries[Key(tenant,id)]=Entry(revision,row?.ownedCopy()) }
    fun live(tenant: String) = entries.filter { (key,e) -> key.tenant==tenant && e.row!=null }.toList().sortedBy { it.first.id }.map { it.second.row!! }
    fun interval(tenant: String,lo: String,hi: String) = entries.filter { (key,_) -> key.tenant==tenant && key.id>=lo && key.id<hi }.mapKeys { it.key.id }.mapValues { it.value.version }
    fun aliasVersions(tenant: String,name: String) = live(tenant).filter { alias(it)==name }.associate { it.id to version(tenant,it.id) }
    fun imageEntries() = array(entries.toList().sortedWith(compareBy({it.first.tenant},{it.first.id})).map { (key,e) -> obj("tenant" to key.tenant,"id" to key.id,"version" to e.version,"row" to e.row) })
}
