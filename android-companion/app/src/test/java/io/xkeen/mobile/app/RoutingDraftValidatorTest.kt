package io.xkeen.mobile.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class RoutingDraftValidatorTest {
    @Test
    fun `valid JSONC does not create a local syntax issue`() {
        val draft = """
            // Comments are accepted in routing JSONC.
            {
              "routing": {
                "rules": [
                  {
                    "type": "field",
                    "outboundTag": "direct"
                  }
                ]
              }
            }
        """.trimIndent()

        val issues = collectLocalRoutingSyntaxIssues(draft)

        assertTrue(issues.isEmpty())
    }

    @Test
    fun `invalid JSONC produces a structured local syntax issue`() {
        val draft = """
            {
              "routing": {
                "comment": "unfinished"
            }
        """.trimIndent()

        val issues = collectLocalRoutingSyntaxIssues(draft)

        assertEquals(1, issues.size)
        assertEquals(RoutingDiagnosticSource.LocalSyntax, issues.single().source)
        assertEquals(RoutingDiagnosticSeverity.Error, issues.single().severity)
        assertEquals("invalid_json_syntax", issues.single().code)
        assertTrue(issues.single().message.contains("JSON/JSONC"))
    }
}
