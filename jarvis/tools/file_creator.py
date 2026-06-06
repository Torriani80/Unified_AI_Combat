import os
from pathlib import Path
from jarvis.utils.logger import log


class FileCreator:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_file(self, path: str, content: str) -> str:
        full_path = self.base_dir / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        log.info(f"Created file: {full_path}")
        return str(full_path)

    def create_html(self, filename: str, html: str) -> str:
        return self.create_file(filename, html)

    def create_python(self, filename: str, code: str) -> str:
        if not filename.endswith(".py"):
            filename += ".py"
        return self.create_file(filename, code)

    def create_script(self, filename: str, code: str) -> str:
        return self.create_file(filename, code)

    def create_json(self, filename: str, data: str) -> str:
        if not filename.endswith(".json"):
            filename += ".json"
        return self.create_file(filename, data)

    def create_markdown(self, filename: str, content: str) -> str:
        if not filename.endswith(".md"):
            filename += ".md"
        return self.create_file(filename, content)

    def create_pdf_report(self, filename: str, content: str) -> str:
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
            from reportlab.lib.styles import getSampleStyleSheet
            if not filename.endswith(".pdf"):
                filename += ".pdf"
            full_path = self.base_dir / filename
            doc = SimpleDocTemplate(str(full_path), pagesize=A4)
            styles = getSampleStyleSheet()
            elements = []
            for line in content.split("\n"):
                if line.strip():
                    elements.append(Paragraph(line, styles["Normal"]))
                    elements.append(Spacer(1, 6))
            doc.build(elements)
            return str(full_path)
        except ImportError:
            return self.create_markdown(filename.replace(".pdf", ".md"), content)

    def list_files(self) -> list:
        return [str(p.relative_to(self.base_dir)) for p in self.base_dir.rglob("*") if p.is_file()]
