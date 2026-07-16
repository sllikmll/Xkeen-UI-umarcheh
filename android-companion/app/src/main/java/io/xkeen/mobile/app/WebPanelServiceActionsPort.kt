package io.xkeen.mobile.app

import kotlinx.coroutines.delay
import org.json.JSONObject

/**
 * Write adapter for the existing Xkeen UI service-control surface.
 *
 * A successful POST is only an accepted command. Every public operation performs fresh status
 * and core reads afterwards and returns that confirmed server snapshot to the controller.
 */
internal class WebPanelServiceActionsPort(
    private val transport: CompanionHttpTransport,
    private val confirmationAttempts: Int = 16,
    private val confirmationDelayMillis: Long = 1_000,
    private val retryDelay: suspend (Long) -> Unit = { delay(it) },
) : ServiceActionsPort {
    init {
        require(confirmationAttempts > 0) { "confirmationAttempts must be positive" }
        require(confirmationDelayMillis >= 0) { "confirmationDelayMillis must not be negative" }
    }

    override suspend fun switchCore(baseUrl: String, core: String): CoreSwitchResult {
        val targetCore = canonicalCoreName(core)
            ?: throw ServiceActionException("Недопустимое ядро: $core.")
        val response = transport.post(
            CompanionHttpRequest(
                baseUrl = baseUrl,
                endpoint = "/api/xkeen/core",
                body = JSONObject().put("core", targetCore.lowercase()).toString(),
            ),
        )
        requireAcceptedServiceCommand(response.body, "переключение ядра")

        val snapshot = awaitConfirmedSnapshot(baseUrl) { current ->
            current.serviceState == ServiceState.Running &&
                current.activeCore.equals(targetCore, ignoreCase = true)
        }
        if (snapshot.serviceState != ServiceState.Running ||
            !snapshot.activeCore.equals(targetCore, ignoreCase = true)
        ) {
            throw ServiceActionException(
                "Сервер принял переключение на $targetCore, но подтвердил состояние " +
                    "${snapshot.serviceState.displayName()} / ${snapshot.activeCore}.",
            )
        }

        return CoreSwitchResult(
            snapshot = snapshot,
            statusSummary = "Сервер подтвердил работу ${snapshot.activeCore}",
            lastOperation = "Ядро изменено на ${snapshot.activeCore}",
            eventTitle = "Ядро изменено",
            eventSubtitle = "${snapshot.activeCore} активно после подтвержденного перезапуска xkeen",
            logMessage = "Сервер подтвердил ядро ${snapshot.activeCore} и работающий xkeen",
        )
    }

    override suspend fun perform(baseUrl: String, action: ServiceAction): ServiceActionResult {
        val response = transport.post(
            CompanionHttpRequest(
                baseUrl = baseUrl,
                endpoint = when (action) {
                    ServiceAction.Start -> "/api/xkeen/start"
                    ServiceAction.Stop -> "/api/xkeen/stop"
                    ServiceAction.Restart -> "/api/restart"
                },
            ),
        )
        requireAcceptedServiceCommand(response.body, action.label.lowercase())

        val expectedState = when (action) {
            ServiceAction.Start,
            ServiceAction.Restart,
            -> ServiceState.Running

            ServiceAction.Stop -> ServiceState.Stopped
        }
        val snapshot = awaitConfirmedSnapshot(baseUrl) { current ->
            current.serviceState == expectedState
        }
        if (snapshot.serviceState != expectedState) {
            throw ServiceActionException(
                "Сервер принял действие «${action.label}», но подтвердил состояние " +
                    snapshot.serviceState.displayName() + ".",
            )
        }

        val lastOperation = when (action) {
            ServiceAction.Start -> "Сервис запущен и проверен сервером"
            ServiceAction.Stop -> "Сервис остановлен и проверен сервером"
            ServiceAction.Restart -> "Перезапуск подтвержден сервером"
        }
        return ServiceActionResult(
            snapshot = snapshot,
            statusSummary = snapshot.serviceState.statusSummary(),
            lastOperation = lastOperation,
            eventTitle = action.label,
            eventSubtitle = lastOperation,
            logMessage = "$lastOperation; активное ядро: ${snapshot.activeCore}",
        )
    }

    override suspend fun load(baseUrl: String): ConfirmedServiceSnapshot {
        val runtimeStatus = parseServiceRuntimeStatus(
            transport.get(
                CompanionHttpRequest(
                    baseUrl = baseUrl,
                    endpoint = "/api/xkeen/status",
                ),
            ).body,
        )
        val coreStatus = parseCoreStatus(
            transport.get(
                CompanionHttpRequest(
                    baseUrl = baseUrl,
                    endpoint = "/api/xkeen/core",
                ),
            ).body,
        )
        val activeCore = runtimeStatus.currentCore
            ?.takeIf { coreStatus.availableCores.hasCore(it) }
            ?: coreStatus.currentCore?.takeIf { coreStatus.availableCores.hasCore(it) }
            ?: coreStatus.availableCores.first()

        return ConfirmedServiceSnapshot(
            serviceState = runtimeStatus.serviceState,
            activeCore = activeCore,
            availableCores = coreStatus.availableCores,
        )
    }

    private suspend fun awaitConfirmedSnapshot(
        baseUrl: String,
        isConfirmed: (ConfirmedServiceSnapshot) -> Boolean,
    ): ConfirmedServiceSnapshot {
        var snapshot = load(baseUrl)
        for (attempt in 1 until confirmationAttempts) {
            if (isConfirmed(snapshot)) return snapshot
            retryDelay(confirmationDelayMillis)
            snapshot = load(baseUrl)
        }
        return snapshot
    }
}

internal data class ServiceRuntimeStatus(
    val serviceState: ServiceState,
    val currentCore: String?,
)

internal class ServiceActionException(message: String, cause: Throwable? = null) :
    Exception(message, cause)

internal fun parseServiceRuntimeStatus(body: String): ServiceRuntimeStatus {
    val payload = try {
        JSONObject(body)
    } catch (error: Exception) {
        throw ServiceActionException(
            "Xkeen UI вернул неожиданный ответ при проверке состояния сервиса.",
            error,
        )
    }
    if (!payload.optBoolean("ok", false)) {
        throw ServiceActionException("Сервер не подтвердил состояние сервиса xkeen.")
    }
    val status = payload.optString("status").trim().lowercase()
    if (!payload.has("running") && status !in setOf("running", "stopped")) {
        throw ServiceActionException("В ответе сервера отсутствует состояние сервиса xkeen.")
    }
    val running = if (payload.has("running")) {
        payload.optBoolean("running", false)
    } else {
        status == "running"
    }
    return ServiceRuntimeStatus(
        serviceState = if (running) ServiceState.Running else ServiceState.Stopped,
        currentCore = canonicalCoreName(payload.optString("core")),
    )
}

internal fun requireAcceptedServiceCommand(body: String, operation: String) {
    val payload = try {
        JSONObject(body)
    } catch (error: Exception) {
        throw ServiceActionException(
            "Xkeen UI вернул неожиданный ответ на $operation.",
            error,
        )
    }
    if (!payload.optBoolean("ok", false)) {
        val message = payload.optString("error").trim().takeIf(String::isNotBlank)
            ?: "Xkeen UI отклонил $operation."
        throw ServiceActionException(message)
    }
}

private fun ServiceState.displayName(): String = when (this) {
    ServiceState.Running -> "работает"
    ServiceState.Stopped -> "остановлен"
    ServiceState.Restarting -> "перезапускается"
}

private fun ServiceState.statusSummary(): String = when (this) {
    ServiceState.Running -> "Сервис работает; состояние подтверждено сервером"
    ServiceState.Stopped -> "Сервис остановлен; состояние подтверждено сервером"
    ServiceState.Restarting -> "Сервер выполняет перезапуск"
}
