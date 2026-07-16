package io.xkeen.mobile.app

import org.json.JSONArray
import org.json.JSONObject

/**
 * Read-only server validation for a routing draft.  Save/apply deliberately remain on their
 * separate port until the next stage, so a validation request cannot persist or restart Xkeen.
 */
internal interface RoutingValidationPort {
    suspend fun validate(
        baseUrl: String,
        document: RoutingDocument,
    ): RoutingServerValidation
}

internal data class RoutingServerValidation(
    val valid: Boolean,
    val message: String,
    val diagnostics: List<RoutingDiagnostic>,
)

internal class WebPanelRoutingValidationPort(
    private val transport: CompanionHttpTransport,
) : RoutingValidationPort {
    override suspend fun validate(
        baseUrl: String,
        document: RoutingDocument,
    ): RoutingServerValidation {
        val response = try {
            transport.post(
                CompanionHttpRequest(
                    baseUrl = baseUrl,
                    endpoint = "/api/mobile/v1/xray/routing/validate",
                    body = JSONObject()
                        .put("document", document.title)
                        .put("content", document.draftContent)
                        .toString(),
                ),
            )
        } catch (error: CompanionTransportException) {
            if (error.failure.statusCode == 404) {
                throw RoutingValidationException(
                    message = "На роутере установлена версия Xkeen UI без API проверки routing. " +
                        "Обновите Xkeen UI на роутере и повторите проверку.",
                    cause = error,
                    diagnosticCode = "validation_endpoint_unavailable",
                )
            }
            throw error
        }
        return parseRoutingValidationResponse(response.body)
    }
}

internal class RoutingValidationException(
    message: String,
    cause: Throwable? = null,
    val diagnosticCode: String = "validation_request_failed",
) :
    Exception(message, cause)

internal fun parseRoutingValidationResponse(body: String): RoutingServerValidation {
    val payload = try {
        JSONObject(body)
    } catch (error: Exception) {
        throw RoutingValidationException(
            "Xkeen UI вернул неожиданный ответ на проверку routing-конфига.",
            error,
        )
    }
    if (!payload.optBoolean("ok", false)) {
        val error = payload.optJSONObject("error")
        throw RoutingValidationException(
            error?.optString("message")?.trim()?.takeIf(String::isNotBlank)
                ?: "Xkeen UI отклонил проверку routing-конфига.",
        )
    }

    val data = payload.optJSONObject("data") ?: throw RoutingValidationException(
        "В ответе Xkeen UI отсутствуют данные проверки routing-конфига.",
    )
    if (!data.has("valid")) {
        throw RoutingValidationException(
            "В ответе Xkeen UI отсутствует результат проверки routing-конфига.",
        )
    }
    val valid = data.optBoolean("valid")
    val diagnostics = parseRoutingDiagnostics(data.optJSONArray("diagnostics"))
    val message = data.optString("message").trim().takeIf(String::isNotBlank)
        ?: if (valid) {
            "Сервер подтвердил конфигурацию Xray."
        } else {
            "Сервер обнаружил ошибки в конфигурации Xray."
        }
    return RoutingServerValidation(
        valid = valid,
        message = message,
        diagnostics = if (!valid && diagnostics.isEmpty()) {
            listOf(
                RoutingDiagnostic(
                    source = RoutingDiagnosticSource.Server,
                    severity = RoutingDiagnosticSeverity.Error,
                    code = "validation_failed",
                    message = message,
                ),
            )
        } else {
            diagnostics
        },
    )
}

private fun parseRoutingDiagnostics(items: JSONArray?): List<RoutingDiagnostic> {
    if (items == null) return emptyList()
    return buildList {
        for (index in 0 until items.length()) {
            val item = items.optJSONObject(index) ?: throw RoutingValidationException(
                "Xkeen UI вернул некорректную диагностику routing-конфига.",
            )
            val message = item.optString("message").trim()
            if (message.isBlank()) {
                throw RoutingValidationException(
                    "Xkeen UI вернул диагностику routing-конфига без текста ошибки.",
                )
            }
            add(
                RoutingDiagnostic(
                    source = RoutingDiagnosticSource.Server,
                    severity = item.optRoutingDiagnosticSeverity(),
                    code = item.optNonBlankString("code"),
                    message = message,
                    hint = item.optNonBlankString("hint"),
                    phase = item.optNonBlankString("phase"),
                    line = item.optPositiveInt("line"),
                    column = item.optPositiveInt("column"),
                    path = item.optNonBlankString("path"),
                ),
            )
        }
    }
}

private fun JSONObject.optRoutingDiagnosticSeverity(): RoutingDiagnosticSeverity =
    when (optString("severity").trim().lowercase()) {
        "info", "ok" -> RoutingDiagnosticSeverity.Info
        "warning", "warn" -> RoutingDiagnosticSeverity.Warning
        else -> RoutingDiagnosticSeverity.Error
    }

private fun JSONObject.optNonBlankString(name: String): String? =
    optString(name).trim().takeIf(String::isNotBlank)

private fun JSONObject.optPositiveInt(name: String): Int? {
    if (!has(name) || isNull(name)) return null
    val value = optInt(name, 0)
    return value.takeIf { it > 0 }
}
