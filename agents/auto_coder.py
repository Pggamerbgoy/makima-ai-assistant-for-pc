"""
agents/auto_coder.py
Write and execute Python code on demand.
"""

import os
import sys
import logging
import subprocess
import tempfile

logger = logging.getLogger("Makima.AutoCoder")

CODES_DIR = "generated_code"


class AutoCoder:

    def __init__(self, ai):
        self.ai = ai
        os.makedirs(CODES_DIR, exist_ok=True)

    def write(self, task: str) -> str:
        """Generate Python code for a task."""
        prompt = (
            f"Write clean, runnable Python code to: {task}\n"
            f"Rules: use only stdlib or common packages, include comments, "
            f"no markdown fences, no explanation — just the code."
        )
        sys_prompt = "You are an expert Python programmer. Write code matching the exact requirements. Output ONLY valid Python code."
        code = self.ai.generate_response(sys_prompt, prompt)
        # Strip any accidental markdown fences
        import re
        code = re.sub(r"```python\s*", "", code)
        code = re.sub(r"```\s*", "", code)
        # Save to file
        fname = "_".join(task.lower().split()[:4]).replace("/", "_") + ".py"
        path = os.path.join(CODES_DIR, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        return f"Code written to {path}. Say 'run code {fname}' to execute it."

    def run(self, script_name: str) -> str:
        """Execute a previously written script."""
        # Try direct path, then CODES_DIR
        if os.path.exists(script_name):
            path = script_name
        else:
            path = os.path.join(CODES_DIR, script_name)
            if not os.path.exists(path):
                return f"Script '{script_name}' not found."

        try:
            result = subprocess.run(
                [sys.executable, path],
                capture_output=True, text=True, timeout=30
            )
            output = result.stdout.strip() or result.stderr.strip()
            if not output:
                output = "Script ran with no output."
            return f"Output: {output[:300]}"
        except subprocess.TimeoutExpired:
            return "Script timed out after 30 seconds."
        except Exception as e:
            return f"Script failed: {e}"

    def explain(self, code: str) -> str:
        resp, _ = self.ai.chat(f"Explain this code in simple terms:\n\n{code}")
        return resp
