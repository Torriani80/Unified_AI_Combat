import csv
import json
from pathlib import Path
from jarvis.utils.logger import log


class DataAnalyzer:
    def read_csv(self, path: str) -> list:
        rows = []
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        return rows

    def read_json(self, path: str) -> dict:
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def read_text(self, path: str) -> str:
        with open(path, encoding="utf-8") as f:
            return f.read()

    def analyze_csv(self, path: str) -> str:
        try:
            rows = self.read_csv(path)
            if not rows:
                return "Empty CSV"
            headers = list(rows[0].keys())
            summary = f"File: {path}\nColumns: {', '.join(headers)}\nRows: {len(rows)}\n\n"
            for col in headers:
                values = [r[col] for r in rows if r[col]]
                nums = []
                for v in values:
                    try:
                        nums.append(float(v.replace(".", "").replace(",", ".")))
                    except:
                        pass
                if nums:
                    summary += f"{col}: min={min(nums):.2f}, max={max(nums):.2f}, avg={sum(nums)/len(nums):.2f}\n"
                else:
                    unique = len(set(values))
                    summary += f"{col}: {len(values)} non-empty, {unique} unique values\n"
            return summary
        except Exception as e:
            return f"Error analyzing CSV: {e}"

    def create_spreadsheet(self, path: str, headers: list, rows: list):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".csv":
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)
        else:
            try:
                import openpyxl
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.append(headers)
                for row in rows:
                    ws.append(row)
                wb.save(str(path))
            except ImportError:
                csv_path = path.with_suffix(".csv")
                with open(csv_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                    writer.writerows(rows)
                log.info(f"openpyxl not installed, saved as CSV: {csv_path}")
        log.info(f"Spreadsheet created: {path}")
