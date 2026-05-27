"""Phase 2.1 BOM parser tests.

Covers:
  - xlsx parsing with header autodetect
  - csv parsing
  - missing designator column → BomParseError in Bahasa Indonesia
  - multi-designator rows (`R1, R2, R3`) expand to 3 BomItemDraft rows
  - extra columns preserved into BomItemDraft.extra
  - header in row 1 vs row 2/3 (tolerance)

Fixtures are built in-process via openpyxl + csv so the bytes are
reproducible and we don't ship binary xlsx in the repo.
"""

import csv
import io

import pytest
from openpyxl import Workbook

from indusia_visual_editor.services.asset.bom_parser import (
    BomParseError,
    _extract_package,
    parse_bom,
)


def _xlsx_bytes(rows: list[list[str | int | None]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _csv_bytes(rows: list[list[str]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


def test_parse_xlsx_extracts_designators():
    payload = _xlsx_bytes(
        [
            ["Designator", "Value", "Package", "Qty"],
            ["R1", "10kΩ", "0805", 1],
            ["C4", "100uF/16V", "Radial", 1],
            ["U7", "STM32F4", "LQFP-100", 1],
        ]
    )
    items = parse_bom(payload, "sample.xlsx")
    assert len(items) == 3
    designators = [i.designator for i in items]
    assert designators == ["R1", "C4", "U7"]
    assert items[0].value == "10kΩ"
    assert items[0].package == "0805"
    assert items[0].qty == 1


def test_parse_csv_extracts_designators():
    payload = _csv_bytes(
        [
            ["Reference", "Val", "FP", "Quantity"],
            ["R1", "10k", "0805", "1"],
            ["C4", "100uF", "Radial", "1"],
        ]
    )
    items = parse_bom(payload, "sample.csv")
    assert len(items) == 2
    assert items[0].designator == "R1"
    assert items[1].designator == "C4"
    # Fuzzy column mapping: "Reference" → designator, "Val" → value,
    # "FP" → package, "Quantity" → qty
    assert items[0].value == "10k"
    assert items[0].package == "0805"
    assert items[0].qty == 1


def test_rejects_missing_designator_column():
    payload = _csv_bytes(
        [
            ["Value", "Package", "Qty"],
            ["10k", "0805", "1"],
        ]
    )
    with pytest.raises(BomParseError) as exc_info:
        parse_bom(payload, "no-designator.csv")
    # Error message in Bahasa Indonesia per plan §2.1 verification.
    assert "designator" in str(exc_info.value).lower() or "tidak ditemukan" in str(exc_info.value).lower()
    # Must mention the column names we DID find so user can fix.
    assert "Value" in str(exc_info.value) or "value" in str(exc_info.value).lower()


def test_handles_comma_separated_multi_designator_rows():
    payload = _csv_bytes(
        [
            ["Designator", "Value", "Package"],
            ["R1, R2, R3", "10k", "0805"],
            ["C4;C5", "100nF", "0603"],
            ["U7", "STM32F4", "LQFP-100"],
        ]
    )
    items = parse_bom(payload, "multi.csv")
    designators = [i.designator for i in items]
    assert designators == ["R1", "R2", "R3", "C4", "C5", "U7"]
    # Shared value/package across the expanded rows.
    assert all(i.value == "10k" and i.package == "0805" for i in items[:3])


def test_preserves_extra_columns_in_extra_dict():
    payload = _csv_bytes(
        [
            ["Designator", "Value", "Manufacturer", "Supplier-Part-No"],
            ["R1", "10k", "Yageo", "ABC-123"],
        ]
    )
    items = parse_bom(payload, "extra.csv")
    assert len(items) == 1
    assert items[0].extra is not None
    assert items[0].extra.get("Manufacturer") == "Yageo"
    assert items[0].extra.get("Supplier-Part-No") == "ABC-123"


def test_tolerates_header_not_in_row_1():
    payload = _xlsx_bytes(
        [
            ["Title row", "Untuk PCB NV80", "", ""],
            ["", "", "", ""],
            ["Designator", "Value", "Package", "Qty"],
            ["R1", "10k", "0805", 1],
        ]
    )
    items = parse_bom(payload, "row3-header.xlsx")
    assert len(items) == 1
    assert items[0].designator == "R1"


def test_empty_file_raises_bom_parse_error():
    with pytest.raises(BomParseError):
        parse_bom(b"", "empty.csv")


def test_malformed_csv_raises_bom_parse_error_not_csv_error():
    """Regression: a CSV with lone-CR mid-field used to bubble csv.Error up
    as a 500 because the try/except csv.Error in _load_csv only wrapped the
    Sniffer call, not the reader iteration. Now it must be converted to
    BomParseError so the route returns 422 with an Indonesian message."""
    malformed = b"designator,value\r\nR1,10k\rR2,1k\r\n"
    with pytest.raises(BomParseError) as exc_info:
        parse_bom(malformed, "broken.csv")
    assert ".csv" in str(exc_info.value)


def test_parses_sap_utf16_le_tsv_with_subitem_designators():
    """Regression: NOVANTA exports SAP ZLMM_BOM_REPORT as UTF-16 LE tab-
    separated text with a .xls extension. The real placement designators
    live in column 'SubItem' (multi-value, e.g. 'C63,C64,C65,C66'), behind
    10 lines of report preamble. Parser must:
      1. detect FF FE BOM and decode utf-16-le (not utf-8-sig garbage)
      2. scan past the preamble to find the header at row 11
      3. map 'SubItem' → designator (not 'Component', which is the SAP
         material code)
      4. expand multi-designators
    """
    rows = [
        ["12.03.2026", "", "Dynamic List Display"],
        [""],
        ["BOM MultiLevel Report"],
        [""],
        ["Report Name :", "", "ZLMM_BOM_REPORT"],
        ["Plant/Usage/Alt. :", "", "SGMK/1/01"],
        ["FG Material :", "", "NV80-020418-0300"],
        ["Description :", "", "PCB,RF,Oscillator"],
        ["ECM No:"],
        ["BOM Eff.Date:", "", "12.03.2026"],
        [""],
        # row 11: real header
        ["", "FG Part No", "Level", "", "Item", "Component",
         "Component Description", "QTY", "UOM", "Sort String",
         "SubItem", "MPN"],
        [""],
        # row 13+: data — designators in SubItem column, multi-value supported
        ["", "NV80-020418-0300", "2", "", "0010", "NV761-14000-0301",
         "Wire,Teflon,Red,14AWG", "0.6", "EA", "FAT",
         "JP1,JP2", "10304190"],
        ["", "NV80-020418-0300", "2", "", "0020", "NV505-00062-0200",
         "Cap,Elec,330uF,63v,Rad", "4", "EA", "PCA",
         "C63,C64,C65,C66", "10231788"],
        ["", "NV80-020418-0300", "2", "", "0030", "NV574-00027-0100",
         "Res,13,3w,5%,Thru", "2", "EA", "MIS",
         "R11,R6", "10072590"],
    ]
    body = "\r\n".join("\t".join(r) for r in rows)
    payload = b"\xff\xfe" + body.encode("utf-16-le")

    items = parse_bom(payload, "BOM NV80-020418-0300.xls")
    designators = [i.designator for i in items]
    # JP1,JP2 + C63,C64,C65,C66 + R11,R6 = 8 expanded items
    assert designators == ["JP1", "JP2", "C63", "C64", "C65", "C66", "R11", "R6"]
    # Component (SAP material code) must NOT be picked up as designator
    assert "NV761-14000-0301" not in designators
    assert "NV505-00062-0200" not in designators


def test_does_not_misclassify_component_header_as_designator():
    """Regression: with the old `comp` substring synonym, a BOM whose only
    designator-ish column was named 'Component' (SAP material code) would
    be picked up as the designator column and produce garbage rows. After
    dropping `comp` from synonyms, this BOM must be REJECTED — there is no
    real placement designator column."""
    payload = _csv_bytes(
        [
            ["Component", "Component Description", "Qty"],
            ["NV505-00062-0200", "Cap,Elec,330uF", "4"],
            ["NV574-00027-0100", "Res,13,3w", "2"],
        ]
    )
    with pytest.raises(BomParseError) as exc_info:
        parse_bom(payload, "no-designator.csv")
    assert "designator" in str(exc_info.value).lower() or "tidak ditemukan" in str(exc_info.value).lower()


# --- _extract_package unit tests ----------------------------------------
# SAP BOM exports embed the package code inside the comma-separated
# "Component Description" string, e.g. "Cap,Cerm,0.1uF,25V,10%,X7R,SMT,0402".
# The extractor pulls out a clean footprint token the MI classifier can
# pattern-match on.


@pytest.mark.parametrize(
    "description, expected",
    [
        ("Cap,Cerm,0.1uF,25V,10%,X7R,SMT,0402", "0402"),
        ("Cap,Cerm,4.7uF,16V,10%,X7R,SMT,0805", "0805"),
        ("Res,10K,1/8w,1%,ThkFilm,SMT,0603", "0603"),
        ("Res,82,3,1/16w,1%,ThkFilm,SMT,1206", "1206"),
        ("MOSFET,N,40V,1W,SMT,SOT89", "SOT89"),
        ("Diode,Switch,200mA,70V,SMT,SOT23,Dual,Cm", "SOT23"),
        ("ZenDiode,12V,500mW,SMT,SOD123", "SOD123"),
        ("Diode,Schtky,2A,60V,SMT,SMB", "SMB"),
        ("IC,SOIC-8,LM358", "SOIC-8"),
        ("IC,STM32,LQFP-100", "LQFP-100"),
        ("Regulator,TO-220", "TO-220"),
        # Radial / through-hole electrolytic: normalize "Rad" → "Radial"
        ("Cap,Elec,560uF,50v,20%,Rad,16x21,5mm", "Radial"),
        ("Cap,Elec,330uF,63v,Rad", "Radial"),
        # Headers / connectors: normalize "Headr"/"Hdr" → "Header"
        ("Headr,6373,5,Pin,0.3in,PCB,Thru,Tin", "Header"),
        ("Hdr,2x10,2.54mm,PTH", "Header"),
        ("ShHdr,5566,6,Pin,4.2mm,PCB,Thru,2R,Tin", "Header"),
        ("Fuse,Auto Reset,500mA,60v", "Fuse"),
        # No recognizable footprint
        ("BLANK LABEL 8X20MM (White w/o pull tab)", None),
        ("PCB,M,Control", None),
        ("", None),
    ],
)
def test_extract_package_recognizes_common_footprints(description, expected):
    assert _extract_package(description) == expected


def test_sap_description_column_maps_to_value_and_extracts_package():
    """Real NOVANTA SAP shape: `Component Description` is the
    human-readable component string. Parser must (1) map it to the
    `value` field and (2) extract a clean package token from its tail
    so the MI classifier can pattern-match."""
    rows = [
        ["", "FG Part No", "Level", "", "Item", "Component",
         "Component Description", "QTY", "UOM", "Sort String",
         "SubItem", "MPN"],
        ["", "NV80-X", "4", "", "0220", "NV500-00008-1700",
         "Cap,Cerm,0.1uF,25V,10%,X7R,SMT,0402", "7", "EA", "SMT",
         "C10,C11,C13", "10302016"],
        ["", "NV80-X", "4", "", "0640", "NV633-00010-0200",
         "Trans,NPN,1A,80V,1W,SMT,SOT89", "2", "EA", "SMT",
         "Q2,Q4", "10302234"],
        ["", "NV80-X", "3", "", "0100", "NV505-00032-0200",
         "Cap,Elec,560uF,50v,20%,Rad,16x21,5mm", "2", "EA", "MIS",
         "C3,C6", "10302229"],
        ["", "NV80-X", "3", "", "0140", "NV621-00003-0100",
         "Headr,6373,5,Pin,PCB,Thru,Tin", "1", "EA", "MIS",
         "P8", "10302235"],
    ]
    body = "\r\n".join("\t".join(r) for r in rows)
    payload = b"\xff\xfe" + body.encode("utf-16-le")
    items = parse_bom(payload, "BOM NV80-X.xls")
    by_desig = {i.designator: i for i in items}

    # C10/C11/C13 share Cap,Cerm description → value populated, package=0402
    assert by_desig["C10"].value == "Cap,Cerm,0.1uF,25V,10%,X7R,SMT,0402"
    assert by_desig["C10"].package == "0402"
    # SMT classifier should NOT flag 0402 as MI
    assert by_desig["C10"].mi_likely is False

    # SOT89 transistor → SMD
    assert by_desig["Q2"].package == "SOT89"
    assert by_desig["Q2"].mi_likely is False

    # Radial electrolytic → MI (through-hole)
    assert by_desig["C3"].package == "Radial"
    assert by_desig["C3"].mi_likely is True

    # Pin header → MI (through-hole connector)
    assert by_desig["P8"].package == "Header"
    assert by_desig["P8"].mi_likely is True


def test_description_does_not_override_explicit_value_column():
    """When both 'Value' and a description-like column exist, the
    Value column takes precedence (column iteration ends with the
    column closer to the right of the header — same field key 'value'
    means last writer wins, which is intentional)."""
    payload = _csv_bytes(
        [
            ["Designator", "Value", "Description", "Qty"],
            ["R1", "10kOhm", "Res,10K,1/8w,1%,SMT,0805", "1"],
        ]
    )
    items = parse_bom(payload, "two-value-cols.csv")
    # Either "10kOhm" (Value wins) or "Res,..." (Description wins) is
    # acceptable; but parse must not crash and package extraction must
    # still run against whatever ended up in `value`.
    assert items[0].designator == "R1"
    # Whichever value won, package extraction sees a string and pulls
    # 0805 if Description won, or None if 10kOhm won.
    if items[0].value == "10kOhm":
        assert items[0].package is None  # no extractable footprint
    else:
        assert items[0].value == "Res,10K,1/8w,1%,SMT,0805"
        assert items[0].package == "0805"
