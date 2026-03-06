"""Reflection checklist and artifact format for Gatekeeper."""
from dataclasses import dataclass
from typing import Optional


def run_reflection_review(reviewer_output: str, planner_output: str, model: Optional[str] = None) -> "ReflectionArtifact":
    """Reflection on review+planner: is decision justified by evidence? Returns artifact."""
    from app.agents import ollama_client
    prompt = f"""You are the **Gatekeeper** (reflection). Review the following Reviewer and Planner output.
Is the recommended decision (Create Issue / Create PR / No action) justified by evidence from the diff or files?
Check: (1) Evidence cited? (2) No unsupported claims? (3) Risk level consistent with changes?

--- Reviewer ---
{reviewer_output}

--- Planner ---
{planner_output}

Respond with:
1. Verdict: PASS or FAIL
2. Findings: bullet list (or "None" if PASS)
"""
    messages = [{"role": "user", "content": prompt}]
    resp = ollama_client.chat(messages, model=model)
    msg = getattr(resp, "message", None)
    text = (getattr(msg, "content", None) or "").strip()
    return _parse_reflection_text(text)


def _parse_reflection_text(text: str) -> "ReflectionArtifact":
    verdict = "FAIL"
    findings = []
    lower = text.lower()
    if "verdict: pass" in lower or text.strip().upper().startswith("PASS"):
        verdict = "PASS"
    if "verdict: fail" in lower:
        verdict = "FAIL"
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("-") or s.startswith("*"):
            findings.append(s.lstrip("-* ").strip())
    return ReflectionArtifact(verdict=verdict, checklist_findings=findings, raw_comment=text[:500])


REFLECTION_CHECKLIST = """
1. Evidence: Does the draft cite evidence from the diff, files, or issue/PR (no unsupported claims)?
2. Tests: For PRs, is a test plan or testing guidance present?
3. Completeness: Are required sections present (e.g. acceptance criteria for issues; behavior change + test plan for PRs)?
4. Policy: No fabricated or misleading information; no silent changes—only suggested improvements when improving.
"""


@dataclass
class ReflectionArtifact:
    """Structured reflection result from Gatekeeper."""
    verdict: str  # "PASS" or "FAIL"
    checklist_findings: list[str]
    raw_comment: Optional[str] = None

    def to_display(self) -> str:
        lines = [f"Verdict: {self.verdict}"]
        if self.checklist_findings:
            lines.append("Findings:")
            for f in self.checklist_findings:
                lines.append(f"  - {f}")
        if self.raw_comment:
            lines.append(self.raw_comment)
        return "\n".join(lines)
