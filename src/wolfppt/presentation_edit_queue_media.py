"""Queued media and embedded-object add operations for the presentation facade."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .image_inputs import InMemoryFile, InMemoryImage
from .presentation_edit_queue_connectors import PresentationConnectorAddQueueMixin


def _queued_path(value: Any) -> Path | InMemoryFile:
    if isinstance(value, InMemoryFile):
        return value
    path = Path(value)
    return path.resolve() if path.exists() else path


class PresentationMediaAddQueueMixin(PresentationConnectorAddQueueMixin):
    def _queue_picture_add(
        self,
        slide_index: int,
        image_path: str | Path,
        x_emu: int,
        y_emu: int,
        cx_emu: int,
        cy_emu: int,
    ) -> None:
        path = _queued_path(image_path)
        self._shape_adds.append(
            ("picture", (slide_index, path, x_emu, y_emu, cx_emu, cy_emu))
        )

    def _queue_picture_replace(
        self,
        slide_index: int,
        relationship_id: str,
        image_path: str | Path | InMemoryImage,
    ) -> None:
        self._picture_replace_edits[(slide_index, relationship_id)] = _queued_path(
            image_path
        )

    def _queue_movie_add(
        self,
        slide_index: int,
        movie_path: str | Path,
        poster_frame_path: str | Path | None,
        x_emu: int,
        y_emu: int,
        cx_emu: int,
        cy_emu: int,
        mime_type: str,
    ) -> None:
        movie = _queued_path(movie_path)
        poster = None if poster_frame_path is None else _queued_path(poster_frame_path)
        self._shape_adds.append(
            (
                "movie",
                (slide_index, movie, poster, x_emu, y_emu, cx_emu, cy_emu, mime_type),
            )
        )

    def _queue_ole_object_add(
        self,
        slide_index: int,
        object_path: str | Path,
        prog_id: str,
        x_emu: int,
        y_emu: int,
        cx_emu: int,
        cy_emu: int,
        icon_path: str | Path | None,
        icon_cx_emu: int,
        icon_cy_emu: int,
    ) -> None:
        embedded = _queued_path(object_path)
        icon = None if icon_path is None else _queued_path(icon_path)
        self._shape_adds.append(
            (
                "ole_object",
                (
                    slide_index,
                    embedded,
                    prog_id,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                    icon,
                    icon_cx_emu,
                    icon_cy_emu,
                ),
            )
        )

    def _queue_group_picture_add(
        self,
        slide_index: int,
        group_index: int,
        child_index: int,
        image_path: str | Path,
        x_emu: int,
        y_emu: int,
        cx_emu: int,
        cy_emu: int,
    ) -> None:
        path = _queued_path(image_path)
        self._shape_adds.append(
            (
                "group_picture",
                (
                    slide_index,
                    group_index,
                    child_index,
                    path,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                ),
            )
        )

    def _queue_nested_group_picture_add(
        self,
        slide_index: int,
        group_index: int,
        nested_group_child_index: int,
        child_index: int,
        image_path: str | Path,
        x_emu: int,
        y_emu: int,
        cx_emu: int,
        cy_emu: int,
    ) -> None:
        path = _queued_path(image_path)
        if self._shape_adds:
            previous_kind, previous_args = self._shape_adds[-1]
            if (
                previous_kind == "nested_group_shape"
                and previous_args
                == (
                    slide_index,
                    group_index,
                    nested_group_child_index,
                )
            ):
                self._shape_adds[-1] = (
                    "nested_group_picture_in_new_group",
                    (
                        slide_index,
                        group_index,
                        nested_group_child_index,
                        child_index,
                        path,
                        x_emu,
                        y_emu,
                        cx_emu,
                        cy_emu,
                    ),
                )
                return
        self._shape_adds.append(
            (
                "nested_group_picture",
                (
                    slide_index,
                    group_index,
                    nested_group_child_index,
                    child_index,
                    path,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                ),
            )
        )

    def _queue_deeper_nested_group_picture_add(
        self,
        slide_index: int,
        group_index: int,
        nested_group_child_index: int,
        deeper_group_child_index: int,
        child_index: int,
        image_path: str | Path,
        x_emu: int,
        y_emu: int,
        cx_emu: int,
        cy_emu: int,
    ) -> None:
        path = _queued_path(image_path)
        self._shape_adds.append(
            (
                "deeper_nested_group_picture",
                (
                    slide_index,
                    group_index,
                    nested_group_child_index,
                    deeper_group_child_index,
                    child_index,
                    path,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                ),
            )
        )

    def _queue_group_ole_object_add(
        self,
        slide_index: int,
        group_index: int,
        child_index: int,
        object_path: str | Path,
        prog_id: str,
        x_emu: int,
        y_emu: int,
        cx_emu: int,
        cy_emu: int,
        icon_path: str | Path | None,
        icon_cx_emu: int,
        icon_cy_emu: int,
    ) -> None:
        embedded = _queued_path(object_path)
        icon = None if icon_path is None else _queued_path(icon_path)
        self._shape_adds.append(
            (
                "group_ole_object",
                (
                    slide_index,
                    group_index,
                    child_index,
                    embedded,
                    prog_id,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                    icon,
                    icon_cx_emu,
                    icon_cy_emu,
                ),
            )
        )

    def _queue_nested_group_ole_object_add(
        self,
        slide_index: int,
        group_index: int,
        nested_group_child_index: int,
        child_index: int,
        object_path: str | Path,
        prog_id: str,
        x_emu: int,
        y_emu: int,
        cx_emu: int,
        cy_emu: int,
        icon_path: str | Path | None,
        icon_cx_emu: int,
        icon_cy_emu: int,
    ) -> None:
        embedded = _queued_path(object_path)
        icon = None if icon_path is None else _queued_path(icon_path)
        if self._shape_adds:
            previous_kind, previous_args = self._shape_adds[-1]
            if (
                previous_kind == "nested_group_shape"
                and previous_args
                == (
                    slide_index,
                    group_index,
                    nested_group_child_index,
                )
            ):
                self._shape_adds[-1] = (
                    "nested_group_ole_object_in_new_group",
                    (
                        slide_index,
                        group_index,
                        nested_group_child_index,
                        child_index,
                        embedded,
                        prog_id,
                        x_emu,
                        y_emu,
                        cx_emu,
                        cy_emu,
                        icon,
                        icon_cx_emu,
                        icon_cy_emu,
                    ),
                )
                return
        self._shape_adds.append(
            (
                "nested_group_ole_object",
                (
                    slide_index,
                    group_index,
                    nested_group_child_index,
                    child_index,
                    embedded,
                    prog_id,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                    icon,
                    icon_cx_emu,
                    icon_cy_emu,
                ),
            )
        )

    def _queue_deeper_nested_group_ole_object_add(
        self,
        slide_index: int,
        group_index: int,
        nested_group_child_index: int,
        deeper_group_child_index: int,
        child_index: int,
        object_path: str | Path,
        prog_id: str,
        x_emu: int,
        y_emu: int,
        cx_emu: int,
        cy_emu: int,
        icon_path: str | Path | None,
        icon_cx_emu: int,
        icon_cy_emu: int,
    ) -> None:
        embedded = _queued_path(object_path)
        icon = None if icon_path is None else _queued_path(icon_path)
        self._shape_adds.append(
            (
                "deeper_nested_group_ole_object",
                (
                    slide_index,
                    group_index,
                    nested_group_child_index,
                    deeper_group_child_index,
                    child_index,
                    embedded,
                    prog_id,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                    icon,
                    icon_cx_emu,
                    icon_cy_emu,
                ),
            )
        )
