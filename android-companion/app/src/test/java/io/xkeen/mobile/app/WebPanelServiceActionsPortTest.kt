package io.xkeen.mobile.app

import kotlinx.coroutines.test.runTest
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class WebPanelServiceActionsPortTest {
    @Test
    fun stopPostsCommandThenReturnsFreshServerStatusAndCore() = runTest {
        val transport = ServiceFakeTransport(
            responses = mapOf(
                RequestKey("POST", "/api/xkeen/stop") to jsonResponse("""{"ok":true}"""),
                RequestKey("GET", "/api/xkeen/status") to jsonResponse(
                    """{"ok":true,"running":false,"status":"stopped","core":null}""",
                ),
                RequestKey("GET", "/api/xkeen/core") to jsonResponse(
                    """{"ok":true,"cores":["xray","mihomo"],"currentCore":"mihomo"}""",
                ),
            ),
        )

        val result = WebPanelServiceActionsPort(transport).perform(
            "https://lab.lan:8443",
            ServiceAction.Stop,
        )

        assertEquals(ServiceState.Stopped, result.snapshot.serviceState)
        assertEquals("Mihomo", result.snapshot.activeCore)
        assertEquals(listOf("Xray", "Mihomo"), result.snapshot.availableCores)
        assertEquals(
            listOf(
                RequestKey("POST", "/api/xkeen/stop"),
                RequestKey("GET", "/api/xkeen/status"),
                RequestKey("GET", "/api/xkeen/core"),
            ),
            transport.requests.map { RequestKey(it.first, it.second.endpoint) },
        )
        assertTrue(transport.requests.all { it.second.baseUrl == "https://lab.lan:8443" })
    }

    @Test
    fun restartUsesLegacyVerifiedEndpointAndDoesNotInferLocalState() = runTest {
        val transport = successfulActionTransport("/api/restart", runtimeCore = "xray")

        val result = WebPanelServiceActionsPort(transport).perform(
            "https://node.lan",
            ServiceAction.Restart,
        )

        assertEquals(RequestKey("POST", "/api/restart"), transport.requestKeys.first())
        assertEquals(ServiceState.Running, result.snapshot.serviceState)
        assertEquals("Xray", result.snapshot.activeCore)
    }

    @Test
    fun coreSwitchSendsCanonicalPayloadAndRequiresMatchingRuntimeCore() = runTest {
        val transport = successfulActionTransport("/api/xkeen/core", runtimeCore = "mihomo")

        val result = WebPanelServiceActionsPort(transport).switchCore(
            "https://node.lan",
            "Mihomo",
        )

        val post = transport.requests.first().second
        assertEquals("mihomo", JSONObject(post.body.orEmpty()).getString("core"))
        assertEquals("Mihomo", result.snapshot.activeCore)
        assertEquals(ServiceState.Running, result.snapshot.serviceState)
    }

    @Test
    fun coreSwitchWaitsForXrayToLeaveTransientStoppedState() = runTest {
        val transport = ServiceFakeTransport(
            responses = mapOf(
                RequestKey("POST", "/api/xkeen/core") to jsonResponse(
                    """{"ok":true,"core":"xray","restarted":true}""",
                ),
                RequestKey("GET", "/api/xkeen/core") to jsonResponse(
                    """{"ok":true,"cores":["xray","mihomo"],"currentCore":"xray"}""",
                ),
            ),
            responseSequences = mapOf(
                RequestKey("GET", "/api/xkeen/status") to listOf(
                    jsonResponse(
                        """{"ok":true,"running":false,"status":"stopped","core":"xray"}""",
                    ),
                    jsonResponse(
                        """{"ok":true,"running":true,"status":"running","core":"xray"}""",
                    ),
                ),
            ),
        )
        val delays = mutableListOf<Long>()

        val result = WebPanelServiceActionsPort(
            transport = transport,
            confirmationAttempts = 3,
            confirmationDelayMillis = 250,
            retryDelay = { delays += it },
        ).switchCore("https://node.lan", "Xray")

        assertEquals(ServiceState.Running, result.snapshot.serviceState)
        assertEquals("Xray", result.snapshot.activeCore)
        assertEquals(listOf(250L), delays)
        assertEquals(
            2,
            transport.requestKeys.count { it == RequestKey("GET", "/api/xkeen/status") },
        )
    }

    @Test
    fun acceptedCommandWithMismatchedConfirmedStateFails() = runTest {
        val transport = ServiceFakeTransport(
            responses = mapOf(
                RequestKey("POST", "/api/xkeen/start") to jsonResponse("""{"ok":true}"""),
                RequestKey("GET", "/api/xkeen/status") to jsonResponse(
                    """{"ok":true,"running":false,"status":"stopped","core":null}""",
                ),
                RequestKey("GET", "/api/xkeen/core") to jsonResponse(
                    """{"ok":true,"cores":["xray"],"currentCore":"xray"}""",
                ),
            ),
        )

        val error = assertThrowsServiceAction {
            WebPanelServiceActionsPort(transport).perform("https://node.lan", ServiceAction.Start)
        }

        assertTrue(error.message.orEmpty().contains("подтвердил состояние остановлен"))
    }

    @Test
    fun runtimeStatusParserRequiresExplicitServerState() {
        val running = parseServiceRuntimeStatus(
            """{"ok":true,"running":true,"status":"running","core":"XRAY"}""",
        )
        val stopped = parseServiceRuntimeStatus(
            """{"ok":true,"running":false,"status":"stopped","core":null}""",
        )

        assertEquals(ServiceState.Running, running.serviceState)
        assertEquals("Xray", running.currentCore)
        assertEquals(ServiceState.Stopped, stopped.serviceState)
        assertNull(stopped.currentCore)
    }
}

private data class RequestKey(val method: String, val endpoint: String)

private class ServiceFakeTransport(
    private val responses: Map<RequestKey, CompanionHttpResponse>,
    private val responseSequences: Map<RequestKey, List<CompanionHttpResponse>> = emptyMap(),
) : CompanionHttpTransport {
    val requests = mutableListOf<Pair<String, CompanionHttpRequest>>()
    private val sequenceIndexes = mutableMapOf<RequestKey, Int>()
    val requestKeys: List<RequestKey>
        get() = requests.map { RequestKey(it.first, it.second.endpoint) }

    override suspend fun get(request: CompanionHttpRequest): CompanionHttpResponse = respond("GET", request)

    override suspend fun post(request: CompanionHttpRequest): CompanionHttpResponse = respond("POST", request)

    override suspend fun delete(request: CompanionHttpRequest): CompanionHttpResponse = respond("DELETE", request)

    private fun respond(method: String, request: CompanionHttpRequest): CompanionHttpResponse {
        requests += method to request
        val key = RequestKey(method, request.endpoint)
        val sequence = responseSequences[key]
        val sequencedResponse = sequence?.let { items ->
            require(items.isNotEmpty()) { "Empty response sequence for $method ${request.endpoint}" }
            val index = sequenceIndexes.getOrDefault(key, 0)
            sequenceIndexes[key] = index + 1
            items[index.coerceAtMost(items.lastIndex)]
        }
        return requireSuccessfulCompanionResponse(
            sequencedResponse ?: responses[key]
                ?: error("No response for $method ${request.endpoint}"),
        )
    }
}

private fun successfulActionTransport(endpoint: String, runtimeCore: String): ServiceFakeTransport =
    ServiceFakeTransport(
        responses = mapOf(
            RequestKey("POST", endpoint) to jsonResponse(
                if (endpoint == "/api/xkeen/core") {
                    """{"ok":true,"core":"$runtimeCore","restarted":true}"""
                } else {
                    """{"ok":true,"restarted":true}"""
                },
            ),
            RequestKey("GET", "/api/xkeen/status") to jsonResponse(
                """{"ok":true,"running":true,"status":"running","core":"$runtimeCore"}""",
            ),
            RequestKey("GET", "/api/xkeen/core") to jsonResponse(
                """{"ok":true,"cores":["xray","mihomo"],"currentCore":"$runtimeCore"}""",
            ),
        ),
    )

private fun jsonResponse(body: String): CompanionHttpResponse = CompanionHttpResponse(
    statusCode = 200,
    body = body,
    headers = emptyMap(),
    contentType = "application/json",
)

private suspend fun assertThrowsServiceAction(block: suspend () -> Unit): ServiceActionException =
    try {
        block()
        throw AssertionError("Expected ServiceActionException")
    } catch (error: ServiceActionException) {
        error
    }
