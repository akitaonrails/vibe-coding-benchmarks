import com.google.gson.*

data class Key(val tenant: String, val id: String)
data class Presence<T>(val present: Boolean, val value: T)
data class Row(val tenant: String, val id: String, val value: Int,
               val alias: Presence<String?>, val note: Presence<JsonElement?>) {
    fun ownedCopy() = copy(note=Presence(note.present,note.value?.deepCopy()))
    fun toJson() = obj("tenant" to tenant,"id" to id,"value" to value).apply {
        if(alias.present) add("alias",alias.value?.let { JsonPrimitive(it) } ?: JsonNull.INSTANCE)
        if(note.present) add("note",note.value?.deepCopy() ?: JsonNull.INSTANCE)
    }
    companion object {
        fun fromJson(input: JsonObject,tenant: String=input.text("tenant"),id: String=input.text("id")) = Row(
            tenant,id,input.number("value"),Presence(input.has("alias"),input["alias"]?.takeUnless { it.isJsonNull }?.asString),
            Presence(input.has("note"),input["note"]?.deepCopy()))
    }
}
data class Entry(val version: Int, val row: Row?)
sealed interface Frame { fun toJson(): JsonObject }
data class BeginFrame(val tenant: String,val request: String,val revision: Int,val count: Int): Frame {
    override fun toJson()=obj("kind" to "BEGIN","tenant" to tenant,"request" to request,"revision" to revision,"count" to count)
}
data class EditFrame(val id: String,val row: Row?): Frame {
    override fun toJson()=obj("kind" to "EDIT","id" to id,"row" to row)
}
data class SealFrame(val revision: Int): Frame { override fun toJson()=obj("kind" to "SEAL","revision" to revision) }
data object TornFrame: Frame { override fun toJson()=obj("kind" to "TORN") }
fun JsonObject.text(key: String): String = get(key).asString
fun JsonObject.number(key: String): Int = get(key).asInt
fun obj(vararg fields: Pair<String, Any?>): JsonObject = JsonObject().apply {
    for ((key, value) in fields) add(key, when(value) {
        null -> JsonNull.INSTANCE
        is Row -> value.toJson()
        is Frame -> value.toJson()
        is JsonElement -> value.deepCopy()
        is String -> JsonPrimitive(value)
        is Number -> JsonPrimitive(value)
        is Boolean -> JsonPrimitive(value)
        else -> error("unsupported JSON field")
    })
}
fun array(values: Iterable<JsonElement?>): JsonArray = JsonArray().apply { values.forEach { add(it?.deepCopy() ?: JsonNull.INSTANCE) } }
fun alias(row: Row?): String? = row?.alias?.value
fun record(tenant: String,id: String,input: JsonObject) = Row.fromJson(input,tenant,id)
fun wire(row: Row?,version: Int): JsonObject? = row?.toJson()?.apply { if(version==1) remove("tenant") }
