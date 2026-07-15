package io.xkeen.mobile.app

import org.json.JSONObject

internal data class CoreStatus(
    val availableCores: List<String>,
    val currentCore: String?,
)

internal interface CoreStatusSource {
    suspend fun load(baseUrl: String): CoreStatus
}

internal class WebPanelCoreStatusSource(
    private val transport: CompanionHttpTransport = HttpUrlConnectionCompanionTransport(),
) : CoreStatusSource {
    override suspend fun load(baseUrl: String): CoreStatus = parseCoreStatus(
        transport.get(
            CompanionHttpRequest(
                baseUrl = baseUrl,
                endpoint = "/api/xkeen/core",
            ),
        ).body,
    )
}

internal class CoreStatusException(message: String, cause: Throwable? = null) :
    Exception(message, cause)

internal fun parseCoreStatus(body: String): CoreStatus {
    val payload = try {
        JSONObject(body)
    } catch (error: Exception) {
        throw CoreStatusException(
            "Xkeen UI вернул неожиданный ответ при загрузке списка ядер.",
            error,
        )
    }
    if (!payload.optBoolean("ok", false)) {
        throw CoreStatusException("Сервер не вернул список доступных ядер.")
    }

    val coresJson = payload.optJSONArray("cores")
        ?: throw CoreStatusException("В ответе сервера отсутствует список ядер.")
    val cores = buildList {
        for (index in 0 until coresJson.length()) {
            canonicalCoreName(coresJson.optString(index))?.let(::add)
        }
    }.distinctBy(String::lowercase)
    if (cores.isEmpty()) {
        throw CoreStatusException("На сервере не найдены поддерживаемые ядра Xray или Mihomo.")
    }

    return CoreStatus(
        availableCores = cores,
        currentCore = canonicalCoreName(payload.optString("currentCore")),
    )
}

internal fun canonicalCoreName(value: String): String? =
    when (value.trim().lowercase()) {
        "xray" -> "Xray"
        "mihomo" -> "Mihomo"
        else -> null
    }
