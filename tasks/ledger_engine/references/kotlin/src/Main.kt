import com.google.gson.JsonParser
fun main() {
    val engine=Engine()
    generateSequence(::readlnOrNull).forEach { println(engine.call(JsonParser.parseString(it).asJsonObject)) }
}
