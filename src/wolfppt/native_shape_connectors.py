"""Native binding wrappers for connector shape operations."""

from __future__ import annotations

import json
from pathlib import Path

from .native_binding import NATIVE_INSTALL_HINT
from .native_results import NativeConnectorAddResult


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
