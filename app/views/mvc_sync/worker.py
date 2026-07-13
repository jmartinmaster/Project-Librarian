from PyQt6.QtCore import QObject, pyqtSignal
import ast
import requests
try:
    import libcst as cst
    from libcst.metadata import PositionProvider
except ImportError:
    cst = None
    PositionProvider = None

class ASTChunkerWorker(QObject):
    """
    Background worker for parsing raw text using AST and CST 
    without blocking the main GUI thread.
    """
    finished = pyqtSignal()
    error = pyqtSignal(str)
    chunks_ready = pyqtSignal(list)

    def __init__(self, raw_text: str):
        super().__init__()
        self.raw_text = raw_text

    def process_text(self):
        try:
            chunks = []
            
            # AST Parsing Logic
            try:
                tree = ast.parse(self.raw_text)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        chunks.append({"type": "class", "name": node.name, "line": node.lineno})
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        chunks.append({"type": "function", "name": node.name, "line": node.lineno})
            except SyntaxError as e:
                # If there's a syntax error, we may still want to try CST or just pass
                pass
                
            # CST Parsing Logic (if libcst is available)
            if cst is not None:
                try:
                    module = cst.parse_module(self.raw_text)
                    # We can use CST for more granular token/chunk extraction if required
                except Exception:
                    pass

            self.chunks_ready.emit(chunks)
            
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()


class AIRequestWorker(QObject):
    """
    Background worker that sends prompt & code edits to local AI endpoint.
    """
    finished = pyqtSignal()
    success = pyqtSignal(str)
    refused = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, url: str, model: str, source_code: str, instruction: str):
        super().__init__()
        self.url = url
        self.model = model
        self.source_code = source_code
        self.instruction = instruction

    def run(self) -> None:
        try:
            url = self.url
            if "localhost" in url:
                url = url.replace("localhost", "127.0.0.1")
                
            prompt = (
                "You are an expert software developer.\n"
                "Here is the source code of a file:\n"
                "```python\n"
                f"{self.source_code}\n"
                "```\n\n"
                f"Instruction: {self.instruction}\n\n"
                "Rules:\n"
                "1. Perform the changes requested by the instruction.\n"
                "2. If you are unable to fulfill the request, or think you cannot do it (e.g. request is ambiguous, impossible, or out of scope), reply with exactly: 'I cannot fulfill this request.' and nothing else.\n"
                "3. Otherwise, return the COMPLETE updated Python source code and nothing else. Do not wrap the code in markdown code blocks like ```python. Return only the raw executable Python code.\n"
                "4. Make sure to remove or resolve the `#AI-request` comment in the updated code so it doesn't run again."
            )
            
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False
            }
            
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            response_text = data.get("response", "").strip()
            
            if not response_text:
                self.error.emit("Ollama returned an empty response.")
                return
            
            refusal_marker = "I cannot fulfill this request."
            if response_text.startswith(refusal_marker) or refusal_marker.lower() in response_text.lower()[:50]:
                self.refused.emit("The AI model determined it cannot fulfill this request.")
                return
            
            # Clean up potential markdown formatting from LLM
            cleaned_code = response_text
            if cleaned_code.startswith("```"):
                lines = cleaned_code.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                cleaned_code = "\n".join(lines)
            
            self.success.emit(cleaned_code)
            
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()


class AIGenerationWorker(QObject):
    """
    Background worker that runs the AI Triad Method Propagation service.
    """
    finished = pyqtSignal()
    success = pyqtSignal(bool, str)

    def __init__(self, model_path: str, view_path: str, controller_path: str):
        super().__init__()
        self.model_path = model_path
        self.view_path = view_path
        self.controller_path = controller_path

    def run(self) -> None:
        """Execute AIGenerationService.process_triad in background."""
        from app.models.ai_generator import AIGenerationService
        try:
            generator = AIGenerationService()
            ok, msg = generator.process_triad(self.model_path, self.view_path, self.controller_path)
            self.success.emit(ok, msg)
        except Exception as e:
            self.success.emit(False, str(e))
        finally:
            self.finished.emit()

