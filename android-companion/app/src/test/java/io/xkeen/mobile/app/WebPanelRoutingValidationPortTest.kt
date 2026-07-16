package io.xkeen.mobile.app

import kotlinx.coroutines.test.runTest
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class WebPanelRoutingValidationPortTest {
    @Test
    fun `validate posts selected document and raw JSONC to mobile contract`() = runTest {
        val transport = RecordingValidationTransport(
            CompanionHttpResponse(
                statusCode = 200,
                body = """
                    {
                      "ok": true,
                      "data": {
                        "valid": true,
                        "message": "Xray подтвердил конфигурацию.",
                        "diagnostics": []
                      }
                    }
                """.trimIndent(),
                headers = emptyMap(),
                contentType = "application/json",
            ),
        )
        val document = demoRoutingState().documents.first().copy(
            draftContent = "// keep JSONC\n{\"routing\":{\"rules\":[]}}",
        )

        val result = WebPanelRoutingValidationPort(transport).validate(
            baseUrl = "https://router.lan:8443",
            document = document,
        )

        assertTrue(result.valid)
        assertEquals("Xray подтвердил конфигурацию.", result.message)
        val request = transport.postedRequest ?: throw AssertionError("POST request was not made")
        assertEquals("https://router.lan:8443", request.baseUrl)
        assertEquals("/api/mobile/v1/xray/routing/validate", request.endpoint)
        val payload = JSONObject(request.body ?: "")
        assertEquals(document.title, payload.getString("document"))
        assertEquals(document.draftContent, payload.getString("content"))
    }

    @Test
    fun `parse maps structured server diagnostic`() {
        val result = parseRoutingValidationResponse(
            """
                {
                  "ok": true,
                  "data": {
                    "valid": false,
                    "message": "Xray отклонил конфигурацию.",
                    "diagnostics": [
                      {
                        "source": "server",
                        "severity": "error",
                        "code": "invalid_json",
                        "message": "Ожидалась запятая.",
                        "hint": "Проверьте правило.",
                        "phase": "syntax",
                        "line": 12,
                        "column": 8,
                        "path": "05_routing.json"
                      }
                    ]
                  }
                }
            """.trimIndent(),
        )

        assertTrue(!result.valid)
        val diagnostic = result.diagnostics.single()
        assertEquals(RoutingDiagnosticSource.Server, diagnostic.source)
        assertEquals(RoutingDiagnosticSeverity.Error, diagnostic.severity)
        assertEquals("invalid_json", diagnostic.code)
        assertEquals("Проверьте правило.", diagnostic.hint)
        assertEquals("syntax", diagnostic.phase)
        assertEquals(12, diagnostic.line)
        assertEquals(8, diagnostic.column)
        assertEquals("05_routing.json", diagnostic.path)
    }

    @Test
    fun `parse rejects malformed validation payload`() {
        val error = try {
            parseRoutingValidationResponse("{\"ok\":true,\"data\":{}}")
            throw AssertionError("Expected RoutingValidationException")
        } catch (error: RoutingValidationException) {
            error
        }

        assertTrue(error.message.orEmpty().contains("результат"))
    }

    @Test
    fun `validate explains that HTTP 404 requires a backend update`() = runTest {
        val transport = RecordingValidationTransport(
            CompanionHttpResponse(
                statusCode = 404,
                body = "",
                headers = emptyMap(),
                contentType = "text/html",
            ),
        )

        val error = try {
            WebPanelRoutingValidationPort(transport).validate(
                baseUrl = "https://router.lan:8443",
                document = demoRoutingState().documents.first(),
            )
            throw AssertionError("Expected RoutingValidationException")
        } catch (error: RoutingValidationException) {
            error
        }

        assertEquals("validation_endpoint_unavailable", error.diagnosticCode)
        assertTrue(error.message.orEmpty().contains("Обновите Xkeen UI"))
        assertTrue(error.cause is CompanionTransportException)
    }
}

private class RecordingValidationTransport(
    private val response: CompanionHttpResponse,
) : CompanionHttpTransport {
    var postedRequest: CompanionHttpRequest? = null

    override suspend fun get(request: CompanionHttpRequest): CompanionHttpResponse =
        error("GET is not expected")

    override suspend fun post(request: CompanionHttpRequest): CompanionHttpResponse {
        postedRequest = request
        return requireSuccessfulCompanionResponse(response)
    }

    override suspend fun delete(request: CompanionHttpRequest): CompanionHttpResponse =
        error("DELETE is not expected")
}
