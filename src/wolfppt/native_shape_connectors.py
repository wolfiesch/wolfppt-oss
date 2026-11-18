"""Native binding wrappers for connector shape operations."""

from __future__ import annotations

import dataclasses
import json
import zipfile
from pathlib import Path

from .native_binding import NATIVE_INSTALL_HINT
from .native_results import NativeConnectorAddResult
from .package_parts import copy_package_with_replacements

# Connector presets the native connector writer does not emit, keyed to the writer preset of
# the same family. Both carry an empty ``a:avLst``, so the written ``p:cxnSp`` differs only in
# ``a:prstGeom/@prst``, which is retagged on the native output.
CONNECTOR_PRESET_WRITER_BASE = {
    "straightConnector1": "line",
    "bentConnector2": "bentConnector3",
    "bentConnector4": "bentConnector3",
    "bentConnector5": "bentConnector3",
    "curvedConnector2": "curvedConnector3",
    "curvedConnector4": "curvedConnector3",
    "curvedConnector5": "curvedConnector3",
}


def _retag_connector_preset(
    output_path: str | Path,
    result: NativeConnectorAddResult,
    preset_geometry: str,
) -> NativeConnectorAddResult:
    """Rewrite the added connector's ``prst`` from its writer base to ``preset_geometry``."""
    base = CONNECTOR_PRESET_WRITER_BASE.get(preset_geometry)
    if base is None:
        return result
    slide_part = result.slide_part.lstrip("/")
    with zipfile.ZipFile(output_path) as package:
        slide_xml = package.read(slide_part)
    opener = f'<p:cxnSp><p:nvCxnSpPr><p:cNvPr id="{result.shape_id}" '.encode()
    geometry = f'<a:prstGeom prst="{base}">'.encode()
    start = slide_xml.find(opener)
    end = slide_xml.find(b"</p:cxnSp>", start) if start >= 0 else -1
    at = slide_xml.find(geometry, start, end) if end >= 0 else -1
    if at < 0:
        raise RuntimeError(
            f"native connector {result.shape_id} in {slide_part} has no "
            f"prst={base} geometry to retag as {preset_geometry}"
        )
    retagged = (
        slide_xml[:at]
        + f'<a:prstGeom prst="{preset_geometry}">'.encode()
        + slide_xml[at + len(geometry) :]
    )
    copy_package_with_replacements(Path(output_path), Path(output_path), {slide_part: retagged})
    return dataclasses.replace(result, preset_geometry=preset_geometry)


def add_group_connector(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
    preset_geometry: str,
    begin_x_emu: int,
    begin_y_emu: int,
    end_x_emu: int,
    end_y_emu: int,
) -> NativeConnectorAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_group_connector_json(
            str(input_path),
            str(output_path),
            slide_index,
            group_index,
            preset_geometry,
            begin_x_emu,
            begin_y_emu,
            end_x_emu,
            end_y_emu,
        )
    )
    return NativeConnectorAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        preset_geometry=payload["preset_geometry"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_connected_group_connector(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
    preset_geometry: str,
    begin_x_emu: int,
    begin_y_emu: int,
    end_x_emu: int,
    end_y_emu: int,
    begin_connection: tuple[int, int] | None,
    end_connection: tuple[int, int] | None,
) -> NativeConnectorAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_connected_group_connector_json(
            str(input_path),
            str(output_path),
            slide_index,
            group_index,
            preset_geometry,
            begin_x_emu,
            begin_y_emu,
            end_x_emu,
            end_y_emu,
            None if begin_connection is None else begin_connection[0],
            None if begin_connection is None else begin_connection[1],
            None if end_connection is None else end_connection[0],
            None if end_connection is None else end_connection[1],
        )
    )
    return NativeConnectorAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        preset_geometry=payload["preset_geometry"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_connected_group_connector_with_auto_shapes(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
    begin_preset_geometry: str,
    begin_x_emu: int,
    begin_y_emu: int,
    begin_cx_emu: int,
    begin_cy_emu: int,
    end_preset_geometry: str,
    end_x_emu: int,
    end_y_emu: int,
    end_cx_emu: int,
    end_cy_emu: int,
    connector_preset_geometry: str,
    connector_begin_x_emu: int,
    connector_begin_y_emu: int,
    connector_end_x_emu: int,
    connector_end_y_emu: int,
    begin_cxn_pt_idx: int,
    end_cxn_pt_idx: int,
) -> NativeConnectorAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_connected_group_connector_with_auto_shapes_json(
            str(input_path),
            str(output_path),
            slide_index,
            group_index,
            begin_preset_geometry,
            begin_x_emu,
            begin_y_emu,
            begin_cx_emu,
            begin_cy_emu,
            end_preset_geometry,
            end_x_emu,
            end_y_emu,
            end_cx_emu,
            end_cy_emu,
            connector_preset_geometry,
            connector_begin_x_emu,
            connector_begin_y_emu,
            connector_end_x_emu,
            connector_end_y_emu,
            begin_cxn_pt_idx,
            end_cxn_pt_idx,
        )
    )
    return NativeConnectorAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        preset_geometry=payload["preset_geometry"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_nested_group_connector(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
    nested_group_child_index: int,
    preset_geometry: str,
    begin_x_emu: int,
    begin_y_emu: int,
    end_x_emu: int,
    end_y_emu: int,
) -> NativeConnectorAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_nested_group_connector_json(
            str(input_path),
            str(output_path),
            slide_index,
            group_index,
            nested_group_child_index,
            preset_geometry,
            begin_x_emu,
            begin_y_emu,
            end_x_emu,
            end_y_emu,
        )
    )
    return NativeConnectorAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        preset_geometry=payload["preset_geometry"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_deeper_nested_group_connector(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
    nested_group_child_index: int,
    deeper_group_child_index: int,
    preset_geometry: str,
    begin_x_emu: int,
    begin_y_emu: int,
    end_x_emu: int,
    end_y_emu: int,
) -> NativeConnectorAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_deeper_nested_group_connector_json(
            str(input_path),
            str(output_path),
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            preset_geometry,
            begin_x_emu,
            begin_y_emu,
            end_x_emu,
            end_y_emu,
        )
    )
    return NativeConnectorAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        preset_geometry=payload["preset_geometry"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_nested_group_connector_in_new_group(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
    preset_geometry: str,
    begin_x_emu: int,
    begin_y_emu: int,
    end_x_emu: int,
    end_y_emu: int,
) -> NativeConnectorAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_nested_group_connector_in_new_group_json(
            str(input_path),
            str(output_path),
            slide_index,
            group_index,
            preset_geometry,
            begin_x_emu,
            begin_y_emu,
            end_x_emu,
            end_y_emu,
        )
    )
    return NativeConnectorAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        preset_geometry=payload["preset_geometry"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_connector(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    preset_geometry: str,
    begin_x_emu: int,
    begin_y_emu: int,
    end_x_emu: int,
    end_y_emu: int,
) -> NativeConnectorAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_connector_json(
            str(input_path),
            str(output_path),
            slide_index,
            CONNECTOR_PRESET_WRITER_BASE.get(preset_geometry, preset_geometry),
            begin_x_emu,
            begin_y_emu,
            end_x_emu,
            end_y_emu,
        )
    )
    result = NativeConnectorAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        preset_geometry=payload["preset_geometry"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )
    return _retag_connector_preset(output_path, result, preset_geometry)


def add_connected_connector(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    preset_geometry: str,
    begin_x_emu: int,
    begin_y_emu: int,
    end_x_emu: int,
    end_y_emu: int,
    begin_connection: tuple[int, int] | None,
    end_connection: tuple[int, int] | None,
) -> NativeConnectorAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_connected_connector_json(
            str(input_path),
            str(output_path),
            slide_index,
            CONNECTOR_PRESET_WRITER_BASE.get(preset_geometry, preset_geometry),
            begin_x_emu,
            begin_y_emu,
            end_x_emu,
            end_y_emu,
            None if begin_connection is None else begin_connection[0],
            None if begin_connection is None else begin_connection[1],
            None if end_connection is None else end_connection[0],
            None if end_connection is None else end_connection[1],
        )
    )
    result = NativeConnectorAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        preset_geometry=payload["preset_geometry"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )
    return _retag_connector_preset(output_path, result, preset_geometry)


def add_connected_connector_with_auto_shapes(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    begin_preset_geometry: str,
    begin_x_emu: int,
    begin_y_emu: int,
    begin_cx_emu: int,
    begin_cy_emu: int,
    end_preset_geometry: str,
    end_x_emu: int,
    end_y_emu: int,
    end_cx_emu: int,
    end_cy_emu: int,
    connector_preset_geometry: str,
    connector_begin_x_emu: int,
    connector_begin_y_emu: int,
    connector_end_x_emu: int,
    connector_end_y_emu: int,
    begin_cxn_pt_idx: int,
    end_cxn_pt_idx: int,
) -> NativeConnectorAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_connected_connector_with_auto_shapes_json(
            str(input_path),
            str(output_path),
            slide_index,
            begin_preset_geometry,
            begin_x_emu,
            begin_y_emu,
            begin_cx_emu,
            begin_cy_emu,
            end_preset_geometry,
            end_x_emu,
            end_y_emu,
            end_cx_emu,
            end_cy_emu,
            CONNECTOR_PRESET_WRITER_BASE.get(connector_preset_geometry, connector_preset_geometry),
            connector_begin_x_emu,
            connector_begin_y_emu,
            connector_end_x_emu,
            connector_end_y_emu,
            begin_cxn_pt_idx,
            end_cxn_pt_idx,
        )
    )
    result = NativeConnectorAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        preset_geometry=payload["preset_geometry"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )
    return _retag_connector_preset(output_path, result, connector_preset_geometry)
