"""
Gatekeeper agent: verifies draft against reflection checklist, outputs PASS/FAIL and artifact.
"""
from typing import Optional

from app.agents import ollama_client
from app.agents.reflection import REFLECTION_CHECKLIST, ReflectionArtifact


def run_gatekeeper(
    title: str,
    body: str,
    is_pr: bool,
    model: Optional[str] = None,
) -> ReflectionArtifact:
    """
    Run Gatekeeper: check draft for unsupported claims, missing evidence, missing tests, policy.
    Returns ReflectionArtifact with verdict PASS/FAIL and checklist findings.
    """
    kind = "Pull Request" if is_pr else "Issue"
    prompt = f"""You are the **Gatekeeper** agent. Verify this {kind} draft against the checklist.

Checklist:
{REFLECTION_CHECKLIST}

--- Draft title ---
{title}

--- Draft body ---
{body}

Respond with:
1. Verdict: PASS or FAIL (one word on its own line).
2. Findings: bullet list of any checklist items that fail or need improvement.
3. Brief comment if FAIL (what to fix).
"""
    messages = [{"role": "user", "content": prompt}]
    resp = ollama_client.chat(messages, model=model)
    text = (getattr(resp.message, "content", None) or "").strip()
    return _parse_reflection(text)


def _parse_reflection(text: str) -> ReflectionArtifact:
    """Parse Gatekeeper response into ReflectionArtifact."""
    verdict = "FAIL"
    findings = []
    raw = text
    lower = text.lower()
    if "verdict: pass" in lower or "\npass\n" in lower or text.strip().upper().startswith("PASS"):
        verdict = "PASS"
    if "verdict: fail" in lower or "verdict:fail" in lower or "\nfail\n" in lower:
        verdict = "FAIL"
    lines = text.split("\n")
    in_findings = False
    for line in lines:
        s = line.strip()
        if "finding" in s.lower() and ":" in s:
            in_findings = True
            continue
        if in_findings and (s.startswith("-") or s.startswith("*")):
            findings.append(s.lstrip("-* ").strip())
        elif in_findings and s and not s.lower().startswith("verdict"):
            findings.append(s)
    return ReflectionArtifact(verdict=verdict, checklist_findings=findings, raw_comment=text[:500])
