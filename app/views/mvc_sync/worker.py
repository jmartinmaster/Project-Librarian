from PyQt6.QtCore import QObject, pyqtSignal
import ast
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
