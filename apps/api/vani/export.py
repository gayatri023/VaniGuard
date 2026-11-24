"""CSV export: one tidy file per table plus commands_flat.csv.  python -m vani.export [out_dir]"""

from __future__ import annotations

import csv
import io
import json
import os
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session, sessionmaker

from .db import Base, CommandRow, SessionRow, make_engine
from .settings import load_dotenv_files


def _cell(v: Any) -> Any:
    return json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v


def flat_csv(db: Session) -> str:
    """commands joined with their session columns (the file the analysis reads)."""
    scols = [c.key for c in inspect(SessionRow).mapper.column_attrs if c.key not in ("deletion_code_hash", "session_id")]
    ccols = [c.key for c in inspect(CommandRow).mapper.column_attrs if c.key != "response_json"]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(ccols + [f"session_{c}" for c in scols])
    for cmd in db.scalars(select(CommandRow).order_by(CommandRow.created_at)):
        s = db.get(SessionRow, cmd.session_id)
        w.writerow([_cell(getattr(cmd, c)) for c in ccols] + [_cell(getattr(s, c)) for c in scols])
    return buf.getvalue()


def export_all(database_url: str, out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    engine = make_engine(database_url)
    Base.metadata.create_all(engine)
    written: list[Path] = []
    with sessionmaker(engine)() as db:
        for table in Base.metadata.sorted_tables:
            if table.name == "deletions":
                continue  # audit record only
            cols = [c.name for c in table.columns if c.name != "deletion_code_hash"]
            path = out / f"{table.name}.csv"
            with path.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(cols)
                for row in db.execute(select(*[table.c[c] for c in cols])).all():
                    w.writerow([_cell(v) for v in row])
            written.append(path)
        flat = out / "commands_flat.csv"
        flat.write_text(flat_csv(db), encoding="utf-8")
        written.append(flat)
    return written


if __name__ == "__main__":
    load_dotenv_files()
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/export")
    for p in export_all(os.environ.get("DATABASE_URL", "sqlite:///./vani.db"), target):
        print(p)
