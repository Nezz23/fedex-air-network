import zipfile

import duckdb
import pytest

from ingestion.load_raw import load

HEADER = "YEAR,MONTH,UNIQUE_CARRIER,ORIGIN,DEST,FREIGHT\n"


def write_zip(path, rows):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("T_T100_SEGMENT_ALL_CARRIER.csv", HEADER + "".join(rows))


def test_loads_every_year_as_text_and_reloading_replaces(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    db = tmp_path / "w.duckdb"
    write_zip(raw / "t100_segment_2024.zip", ["2024,1,FX,MEM,IND,100.00\n", "2024,1,5X,SDF,ONT,50.00\n"])
    write_zip(raw / "t100_segment_2025.zip", ["2025,2,FX,MEM,OAK,7.50\n"])

    assert load(db, raw) == {2024: 2, 2025: 1}
    assert load(db, raw) == {2024: 2, 2025: 1}  # idempotent: a year is replaced, not appended

    con = duckdb.connect(str(db))
    assert con.execute("select count(*) from raw.t100_segment").fetchone()[0] == 3
    assert con.execute("select typeof(freight) from raw.t100_segment limit 1").fetchone()[0] == "VARCHAR"
    assert con.execute("select distinct source_file from raw.t100_segment order by 1").fetchall() == [
        ("t100_segment_2024.zip",), ("t100_segment_2025.zip",)]


def test_a_file_with_rows_from_another_year_is_refused(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    write_zip(raw / "t100_segment_2024.zip", ["2023,12,FX,MEM,IND,1\n"])
    with pytest.raises(ValueError, match="not from 2024"):
        load(tmp_path / "w.duckdb", raw)
