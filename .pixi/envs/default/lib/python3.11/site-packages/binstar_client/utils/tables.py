# -*- coding: utf-8 -*-

"""Utility to print tables to terminal."""

__all__ = ()

import itertools
import math
import typing

if typing.TYPE_CHECKING:
    import typing_extensions

    Alignment: 'typing_extensions.TypeAlias' = typing_extensions.Literal['<', '^', '>']


def lcm(left: int, right: int) -> int:
    """Find the least common multiple of two numbers."""
    if left == 0:
        left = 1
    if right == 0:
        right = 1
    return left * right // math.gcd(left, right)


ANY: 'typing_extensions.Final[str]' = '*'
COMBINATIONS: 'typing_extensions.Final[typing.Dict[int, typing.Sequence[typing.Tuple[int, ...]]]]' = {}
EMPTY: 'typing_extensions.Final[str]' = '∅'


class ValuesView(typing.Mapping[typing.Tuple[str, ...], str]):
    """
    Helper view which allows parent collection to have patterns as its keys.

    Each key of the parent collection should be a tuple of strings of a particular length (defined via
    :code:`key_length` argument). In case you don't use patterns for your original collections keys - this view would
    return only full values for fully matched keys.

    For a key to become a pattern - it is enough to set any part to :code:`ANY` (or :code:`'*'`). Basically, this value
    means that on this particular place there might be any string value. If you request a value for some key tuple and
    everything matches except :code:`ANY` key parts - corresponding value might be returned to the user. Unless there is
    another value where key matches with less number of :code:`ANY` entries.

    .. warning::
        Patterns might be used only on the parent collection side. Each :code:`ANY` in your requested key would be
        treated as an exact value.

    :param content: Parent collection to look for values in.
    :param key_length: Length of a tuple keys used for this collection.
    :param default: Value to use on each lookup miss.
    """

    __slots__ = ('__content', '__default', '__key_length')

    def __init__(
            self,
            content: typing.Mapping[typing.Tuple[str, ...], str],
            key_length: int,
            *,
            default: typing.Optional[str] = None,
    ) -> None:
        """Initialize new :class:`~ValuesView` instance."""
        self.__content: 'typing_extensions.Final[typing.Mapping[typing.Tuple[str, ...], str]]' = content
        self.__default: 'typing_extensions.Final[typing.Optional[str]]' = default
        self.__key_length: 'typing_extensions.Final[int]' = key_length

        if key_length not in COMBINATIONS:
            COMBINATIONS[key_length] = [
                indexes
                for step in range(self.__key_length + 1)
                for indexes in itertools.combinations(range(self.__key_length), step)
            ]

    def __getitem__(self, key: typing.Tuple[str, ...]) -> str:
        """Retrieve a value for the :code:`key`."""
        if len(key) != self.__key_length:
            raise ValueError('invalid length of a key')

        combination: typing.Tuple[int, ...]
        for combination in COMBINATIONS[self.__key_length]:
            current_key = tuple(
                ANY if (index in combination) else value
                for index, value in enumerate(key)
            )
            try:
                return self.__content[current_key]
            except KeyError:
                continue

        if self.__default is not None:
            return self.__default

        raise KeyError(f'no value found for {key}')

    def __iter__(self) -> typing.Iterator[typing.Tuple[str, ...]]:
        """Iterate through registered keys and patterns."""
        return iter(self.__content)

    def __len__(self) -> int:
        """Retrieve total number of records in the collection."""
        return len(self.__content)


class TableDesign:
    """
    Definition of the design used for table borders.

    This design allows you to set borders between cells of different kinds. It is up to you to define cell kinds - no
    strict limitations here.
    """

    __slots__ = (
        '__horizontal', '__horizontal_view',
        '__intersection', '__intersection_view',
        '__vertical', '__vertical_view',
    )

    def __init__(self) -> None:
        """Initialize new :class:`~TableDesign` instance."""
        self.__horizontal: 'typing_extensions.Final[typing.Dict[typing.Tuple[str, ...], str]]' = {}
        self.__horizontal_view: 'typing_extensions.Final[ValuesView]' = ValuesView(self.__horizontal, 2, default='')

        self.__intersection: 'typing_extensions.Final[typing.Dict[typing.Tuple[str, ...], str]]' = {}
        self.__intersection_view: 'typing_extensions.Final[ValuesView]' = ValuesView(self.__intersection, 4, default='')

        self.__vertical: 'typing_extensions.Final[typing.Dict[typing.Tuple[str, ...], str]]' = {}
        self.__vertical_view: 'typing_extensions.Final[ValuesView]' = ValuesView(self.__vertical, 2, default='')

    @property
    def horizontal(self) -> ValuesView:  # noqa: D401
        """Horizontal borders between cells above it and below it."""
        return self.__horizontal_view

    @property
    def intersection(self) -> ValuesView:
        """Intersection between the cells on the top-left, top-right, bottom-left and bottom right of it."""
        return self.__intersection_view

    @property
    def vertical(self) -> ValuesView:
        """Vertical borders between cells on the left of it and on the right"""
        return self.__vertical_view

    def with_border_style(  # pylint: disable=too-many-arguments
            self,
            horizontal: str,
            vertical: str,
            corner_nw: str,
            corner_ne: str,
            corner_se: str,
            corner_sw: str,
    ) -> 'TableDesign':
        """
        Define a style for an external border of the table.

        .. warning::

            This would create a new :class:`~TableDesign` with requested modifications. There would be no modifications
            to the original instance.
        """
        # pylint: disable=protected-access
        result: 'TableDesign' = self.__copy()
        result.__horizontal[EMPTY, ANY] = horizontal
        result.__horizontal[ANY, EMPTY] = horizontal
        result.__intersection[EMPTY, EMPTY, EMPTY, ANY] = corner_nw
        result.__intersection[EMPTY, EMPTY, ANY, EMPTY] = corner_ne
        result.__intersection[EMPTY, ANY, EMPTY, EMPTY] = corner_sw
        result.__intersection[ANY, EMPTY, EMPTY, EMPTY] = corner_se
        result.__vertical[EMPTY, ANY] = vertical
        result.__vertical[ANY, EMPTY] = vertical
        return result

    def with_border_transition(  # pylint: disable=too-many-arguments
            self,
            kind: str,
            top: str,
            right: str,
            bottom: str,
            left: str,
    ) -> 'TableDesign':
        """
        Define how external border should transition into borders of a :code:`kind`.

        .. warning::

            This would create a new :class:`~TableDesign` with requested modifications. There would be no modifications
            to the original instance.
        """
        # pylint: disable=protected-access
        result: 'TableDesign' = self.__copy()
        result.__intersection[EMPTY, EMPTY, kind, kind] = top
        result.__intersection[EMPTY, kind, EMPTY, kind] = left
        result.__intersection[kind, EMPTY, kind, EMPTY] = right
        result.__intersection[kind, kind, EMPTY, EMPTY] = bottom
        return result

    def with_cell_style(
            self,
            kind: str,
            horizontal: str,
            vertical: str,
            intersection: str,
    ) -> 'TableDesign':
        """
        Define the borders between cells of the same :code:`kind`.

        .. warning::

            This would create a new :class:`~TableDesign` with requested modifications. There would be no modifications
            to the original instance.
        """
        # pylint: disable=protected-access
        result: 'TableDesign' = self.__copy()
        result.__horizontal[kind, kind] = horizontal
        result.__intersection[kind, kind, kind, kind] = intersection
        result.__vertical[kind, kind] = vertical
        return result

    def with_horizontal(
            self,
            top_kind: str,
            bottom_kind: str,
            value: str,
    ) -> 'TableDesign':
        """
        Define a single horizontal border rule.

        .. warning::

            This would create a new :class:`~TableDesign` with requested modifications. There would be no modifications
            to the original instance.
        """
        # pylint: disable=protected-access
        result: 'TableDesign' = self.__copy()
        result.__horizontal[top_kind, bottom_kind] = value
        return result

    def with_intersection(  # pylint: disable=too-many-arguments
            self,
            top_left_kind: str,
            top_right_kind: str,
            bottom_left_kind: str,
            bottom_right_kind: str,
            value: str,
    ) -> 'TableDesign':
        """
        Define a single intersection border rule.

        .. warning::

            This would create a new :class:`~TableDesign` with requested modifications. There would be no modifications
            to the original instance.
        """
        # pylint: disable=protected-access
        result: 'TableDesign' = self.__copy()
        result.__intersection[top_left_kind, top_right_kind, bottom_left_kind, bottom_right_kind] = value
        return result

    def with_vertical(
            self,
            left_kind: str,
            right_kind: str,
            value: str,
    ) -> 'TableDesign':
        """
        Define a single vertical border rule.

        .. warning::

            This would create a new :class:`~TableDesign` with requested modifications. There would be no modifications
            to the original instance.
        """
        # pylint: disable=protected-access
        result: 'TableDesign' = self.__copy()
        result.__vertical[left_kind, right_kind] = value
        return result

    def __copy(self) -> 'TableDesign':
        """
        Create a full copy of the current instance.

        Used for safe modifications without any changes to the original value.
        """
        # pylint: disable=protected-access
        result: 'TableDesign' = TableDesign()
        result.__horizontal.update(self.__horizontal)
        result.__intersection.update(self.__intersection)
        result.__vertical.update(self.__vertical)
        return result


class TableCell:
    """
    General definition of a table cell.

    :param kind: Kind of the cell (used for styling purposes, see :class:`~TableDesign`).
    :param value: Exact content of the cell.
    :param alignment: How text should be aligned in the cell.
    """

    __slots__ = ('alignment', 'kind', 'value')

    def __init__(
            self,
            kind: str,
            value: typing.Any,
            *,
            alignment: 'Alignment' = '<',
    ) -> None:
        """Initialize new :class:`~TableCell` instance."""
        if value is None:
            value = ''

        self.alignment: 'Alignment' = alignment
        self.kind: str = kind
        self.value: str = str(value)

    def __repr__(self) -> str:
        """Prepare a string representation of the instance."""
        return f'{type(self).__name__}(kind={self.kind!r}, value={self.value!r}, alignment={self.alignment!r})'

    def __str__(self) -> str:
        """Prepare a string representation of the instance."""
        return self.value


EMPTY_CELL: 'typing_extensions.Final[TableCell]' = TableCell(kind=EMPTY, value='')
TEMPLATE: str = '{{: {1}{0}.{0}s}}'


class TableCore:
    """
    Core for any table implementation.

    It is used to store the whole table data and visualize it.

    :param default: What to show for cells with no values.
    """

    __slots__ = ('__columns', '__content', '__default', '__rows')

    def __init__(self, *, default: TableCell) -> None:
        """Initialize new :class:`~TableCore` instance."""
        self.__columns: typing.Optional[int] = 0
        self.__content: 'typing_extensions.Final[typing.List[typing.List[typing.Optional[TableCell]]]]' = []
        self.__default: TableCell = default
        self.__rows: typing.Optional[int] = 0

    @property
    def columns(self) -> int:  # noqa: D401
        """Total number o columns in this table."""
        if self.__columns is None:
            self.__columns = max(map(len, self.__content))
        return self.__columns

    @property
    def default(self) -> TableCell:  # noqa: D401
        """Default cell content to show for empty cells."""
        return self.__default

    @default.setter
    def default(self, value: TableCell) -> None:
        """Update the `default` value."""
        self.__default = value

    @property
    def rows(self) -> int:  # noqa: D401
        """Total number of rows in this table."""
        if self.__rows is None:
            self.__rows = len(self.__content)
        return self.__rows

    def append_row(self, values: typing.Iterable[typing.Optional[TableCell]]) -> None:
        """Append new row to the bottom of this table."""
        row: typing.List[typing.Optional[TableCell]] = list(values)
        self.__content.append(row)
        if self.__columns is not None:
            self.__columns = max(self.__columns, len(row))
        if self.__rows is not None:
            self.__rows += 1

    def remove_column(self, column: int) -> None:
        """Remove a single column from the table."""
        row: typing.List[typing.Optional[TableCell]]
        for row in self.__content:
            try:
                del row[column]
            except IndexError:
                pass
        if self.__columns is not None:
            self.__columns -= 1

    def remove_row(self, row: int) -> None:
        """Remove a single row from the table."""
        try:
            del self.__content[row]
        except IndexError:
            pass
        if self.__rows is not None:
            self.__rows -= 1

    def render(self, design: TableDesign) -> typing.Iterator[str]:
        """Print table to the user (in terminal)."""
        empty_row = [EMPTY_CELL] * self.columns
        widths: typing.Sequence[int] = self.__render_analysis(design=design)

        current: typing.Sequence[typing.Optional[TableCell]]
        previous: typing.Sequence[typing.Optional[TableCell]] = empty_row
        for current in self.__content:
            yield from self.__render_separator(above_row=previous, below_row=current, widths=widths, design=design)
            yield from self.__render_row(row=current, widths=widths, design=design)
            previous = current
        yield from self.__render_separator(above_row=previous, below_row=empty_row, widths=widths, design=design)

    def trim(
            self,
            *,
            empty_columns: bool = False,
            empty_rows: bool = False,
            empty_values: bool = False,
    ) -> typing.Tuple[typing.List[int], typing.List[int]]:
        """
        Remove trailing empty cells from each row.

        :param empty_columns: Also remove columns if all of their cells are empty.
        :param empty_rows: Also remove rows if all of their cells are empty
        :param empty_values: If any cell contains an empty value - convert it to empty cell.

                             This action is performed before anything else.

        :return: Lists of removed columns and rows
        """
        removed_columns: typing.List[int] = []
        removed_columns_offset: int = 0
        removed_rows: typing.List[int] = []
        removed_rows_offset: int = 0

        index: int = 0
        while index < len(self.__content):
            # remove cells with empty values
            if empty_values:
                self.__content[index] = [
                    cell if (cell is not None) and cell.value else None
                    for cell in self.__content[index]
                ]

            # remove trailing columns
            while self.__content[index] and (self.__content[index][-1] is None):
                self.__content[index].pop()

            # remove empty rows if requested
            if (not self.__content[index]) and empty_rows:
                self.remove_row(index)
                removed_rows.append(removed_rows_offset + index)
                removed_rows_offset += 1
            else:
                index += 1

        # remove trailing empty rows
        while self.__content and (not self.__content[-1]):
            self.remove_row(-1)

        # remove empty columns
        index = 0
        while empty_columns:
            no_column: bool = True
            has_value: bool = False

            row: typing.List[typing.Optional[TableCell]]
            for row in self.__content:
                try:
                    has_value |= row[index] is not None
                except LookupError:
                    continue
                else:
                    no_column = False

            if no_column:
                break
            if has_value:
                index += 1
                continue

            self.remove_column(index)
            removed_columns.append(removed_columns_offset + index)
            removed_columns_offset += 1

        # invalidate counters
        self.__columns = None
        self.__rows = None

        # return result
        return removed_columns, removed_rows

    def __iterate_row(self, row: typing.Iterable[typing.Optional[TableCell]]) -> typing.Iterator[TableCell]:
        """
        Iterate all cells in a single row.

        This may add trailing cells to ensure the number of columns.
        """
        for value in itertools.islice(itertools.chain(row, itertools.repeat(self.__default)), self.__columns):
            yield value or self.__default

    def __render_analysis(self, design: TableDesign) -> typing.Sequence[int]:
        """Measure each column and vertical border."""
        curr: typing.Sequence[typing.Optional[TableCell]]
        curr_cell: TableCell
        curr_prev: str

        prev: typing.Sequence[typing.Optional[TableCell]]
        prev_cell: TableCell
        prev_prev: str

        index: int
        temp: int

        steps: typing.List[int] = [1] * (2 * self.columns + 1)
        widths: typing.List[int] = [0] * (2 * self.columns + 1)

        # analysis
        prev = [EMPTY_CELL] * self.columns
        for curr in self.__content:
            index = 0
            curr_prev = EMPTY
            prev_prev = EMPTY
            for prev_cell, curr_cell in zip(self.__iterate_row(prev), self.__iterate_row(curr)):
                widths[index] = max(
                    widths[index],
                    len(design.intersection[prev_prev, prev_cell.kind, curr_prev, curr_cell.kind]),
                    len(design.vertical[curr_prev, curr_cell.kind]),
                )
                index += 1

                steps[index] = lcm(steps[index], len(design.horizontal[prev_cell.kind, curr_cell.kind]))
                widths[index] = max(widths[index], len(curr_cell.value))
                index += 1

                prev_prev = prev_cell.kind
                curr_prev = curr_cell.kind

            widths[index] = max(
                widths[index],
                len(design.intersection[prev_prev, EMPTY, curr_prev, EMPTY]),
                len(design.vertical[curr_prev, EMPTY]),
            )

            prev = curr

        index = 0
        prev_prev = EMPTY
        for prev_cell in self.__iterate_row(prev):
            widths[index] = max(widths[index], len(design.intersection[prev_prev, prev_cell.kind, EMPTY, EMPTY]))
            index += 1

            steps[index] = lcm(steps[index], len(design.horizontal[prev_cell.kind, EMPTY]))
            index += 1

            prev_prev = prev_cell.kind
        widths[index] = max(widths[index], len(design.intersection[prev_prev, EMPTY, EMPTY, EMPTY]))

        # normalization
        for index in range(len(widths)):  # pylint: disable=consider-using-enumerate
            temp = widths[index] % steps[index]
            if temp > 0:
                widths[index] += steps[index] - temp

        # result
        return widths

    def __render_row(
            self,
            row: typing.Sequence[typing.Optional[TableCell]],
            widths: typing.Iterable[int],
            design: TableDesign,
    ) -> typing.Iterator[str]:
        """Render a row with values."""
        cell: typing.Optional[TableCell]
        result: str = ''
        previous_kind: str = EMPTY
        widths = iter(widths)
        for cell in self.__iterate_row(row):
            result += TEMPLATE.format(next(widths, 0), '^').format(design.vertical[previous_kind, cell.kind])
            result += TEMPLATE.format(next(widths, 0), cell.alignment).format(cell.value)
            previous_kind = cell.kind
        yield result + design.vertical[previous_kind, EMPTY]

    def __render_separator(
            self,
            above_row: typing.Sequence[typing.Optional[TableCell]],
            below_row: typing.Sequence[typing.Optional[TableCell]],
            widths: typing.Iterable[int],
            design: TableDesign,
    ) -> typing.Iterator[str]:
        """Render a string that contains of horizontal separators and intersections."""
        above_cell: typing.Optional[TableCell]
        above_kind: str = EMPTY
        below_cell: typing.Optional[TableCell]
        below_kind: str = EMPTY
        good: bool = False
        result: str = ''
        widths = iter(widths)
        for above_cell, below_cell in zip(self.__iterate_row(above_row), self.__iterate_row(below_row)):
            result += TEMPLATE.format(next(widths, 0), '^').format(
                design.intersection[above_kind, above_cell.kind, below_kind, below_cell.kind],
            )
            temp = design.horizontal[above_cell.kind, below_cell.kind]
            if temp:
                good = True
                result += temp * (next(widths, 0) // len(temp))
            else:
                result += ' ' * next(widths, 0)
            above_kind = above_cell.kind
            below_kind = below_cell.kind
        if good:
            yield result + TEMPLATE.format(next(widths, 0), '^').format(
                design.intersection[above_kind, EMPTY, below_kind, EMPTY],
            )

    def __delitem__(self, cell: typing.Tuple[int, int]) -> None:
        """Remove a single cell from the table (set it to empty)."""
        try:
            self.__content[cell[0]][cell[1]] = None
        except IndexError:
            pass

    def __getitem__(self, cell: typing.Tuple[int, int]) -> TableCell:
        """Retrieve a single cell from the table."""
        try:
            return self.__content[cell[0]][cell[1]] or self.__default
        except IndexError:
            return self.__default

    def __setitem__(self, cell: typing.Tuple[int, int], value: TableCell) -> None:
        """Update a single cell in a table."""
        while len(self.__content) <= cell[0]:
            self.__content.append([])
        while len(self.__content[cell[0]]) <= cell[1]:
            self.__content[cell[0]].append(None)
        self.__content[cell[0]][cell[1]] = value

        if self.__columns is not None:
            self.__columns = max(self.__columns, cell[1] + 1)
        if self.__rows is not None:
            self.__rows = max(self.__rows, cell[0] + 1)


HEADING: 'typing_extensions.Final[str]' = 'H'
CELL: 'typing_extensions.Final[str]' = 'C'


class SimpleTable:
    """
    Table with headings.

    :param heading_rows: How many rows should be used as a headings.
    :param heading_columns: How many columns should be used as a headings.
    """

    __slots__ = ('__alignment', '__clean', '__core', '__heading_columns', '__heading_rows')

    def __init__(
            self,
            heading_rows: int = 0,
            heading_columns: int = 0,
    ) -> None:
        """Initialize new :class:`~SimpleTable` instance."""
        self.__alignment: typing.Dict[typing.Tuple[int, int], 'Alignment'] = {(-1, -1): '<'}
        self.__clean: bool = True
        self.__core: 'typing_extensions.Final[TableCore]' = TableCore(default=TableCell(kind=CELL, value=''))
        self.__heading_columns: 'typing_extensions.Final[int]' = heading_columns
        self.__heading_rows: 'typing_extensions.Final[int]' = heading_rows

    @property
    def alignment(self) -> 'Alignment':  # noqa: D401
        """Default alignment value for all cells."""
        return self.__alignment[-1, -1]

    @alignment.setter
    def alignment(self, value: 'Alignment') -> None:
        """Update default alignment value."""
        self.__alignment[-1, -1] = value

    @property
    def columns(self) -> int:  # noqa: D401
        """Number of columns in this table."""
        return self.__core.columns

    @property
    def rows(self) -> int:  # noqa: D401
        """Number of rows in this table."""
        return self.__core.rows

    def align_cell(self, row: int, column: int, alignment: 'Alignment') -> None:
        """Align a single cell in the table."""
        if row < 0:
            raise AttributeError(f'row index must be at least 0, not {row}')
        if column < 0:
            raise AttributeError(f'column index must be at least 0, not {column}')

        self.__alignment[row, column] = alignment
        self.__clean = False

    def align_column(self, column: int, alignment: 'Alignment') -> None:
        """Align each cell in a single column of the table."""
        new_alignment: typing.Dict[typing.Tuple[int, int], 'Alignment'] = {
            key: value
            for key, value in self.__alignment.items()
            if key[1] != column
        }
        new_alignment[-1, column] = alignment
        self.__alignment = new_alignment
        self.__clean = False

    def align_row(self, row: int, alignment: 'Alignment') -> None:
        """Aline each cell in a single row of the table."""
        new_alignment: typing.Dict[typing.Tuple[int, int], 'Alignment'] = {
            key: value
            for key, value in self.__alignment.items()
            if key[0] != row
        }
        new_alignment[row, -1] = alignment
        self.__alignment = new_alignment
        self.__clean = False

    def append_row(self, values: typing.Iterable[typing.Any]) -> None:
        """Append new row to the bottom of this table."""
        self.__core.append_row([TableCell(kind=CELL, value=value) for value in values])
        self.__clean = False

    def remove_column(self, column: int) -> None:
        """Remove a single column from the table."""
        self.__core.remove_column(column)
        new_alignment: typing.Dict[typing.Tuple[int, int], 'Alignment'] = {
            (key_row, key_column - (key_column > column)): value
            for (key_row, key_column), value in self.__alignment.items()
            if key_column != column
        }
        self.__alignment = new_alignment
        self.__clean = False

    def remove_row(self, row: int) -> None:
        """Remove a single row from the table."""
        self.__core.remove_row(row)
        new_alignment: typing.Dict[typing.Tuple[int, int], 'Alignment'] = {
            (key_row - (key_row > row), key_column): value
            for (key_row, key_column), value in self.__alignment.items()
            if key_row != row
        }
        self.__alignment = new_alignment
        self.__clean = False

    def render(self, design: TableDesign) -> typing.Iterator[str]:
        """Print table to the user (in terminal)."""
        self._normalize()
        return self.__core.render(design)

    def trim(self, *, empty_columns: bool = False, empty_rows: bool = False, empty_values: bool = False) -> None:
        """
        Remove trailing empty cells from each row.

        :param empty_columns: Also remove columns if all of their cells are empty.
        :param empty_rows: Also remove rows if all of their cells are empty
        :param empty_values: If any cell contains an empty value - convert it to empty cell.

                             This action is performed before anything else.
        """
        removed_columns: typing.Sequence[int]
        removed_rows: typing.Sequence[int]
        removed_columns, removed_rows = self.__core.trim(
            empty_columns=empty_columns,
            empty_rows=empty_rows,
            empty_values=empty_values,
        )

        new_alignment: typing.Dict[typing.Tuple[int, int], 'Alignment'] = {
            (
                key_row - sum(key_row > row for row in removed_rows),
                key_column - sum(key_column > column for column in removed_columns),
            ): value
            for (key_row, key_column), value in self.__alignment.items()
            if (key_column not in removed_columns) and (key_row not in removed_rows)
        }
        self.__alignment = new_alignment

        self.__clean = False

    def _normalize(self) -> None:
        """Apply table visualization preferences to the table (e.g. alignments)."""
        if self.__clean:
            return

        for row in range(self.__core.rows):
            for column in range(self.__core.columns):
                kind: str
                if (row < self.__heading_rows) or (column < self.__heading_columns):
                    kind = HEADING
                else:
                    kind = CELL

                alignment: 'Alignment' = (
                        self.__alignment.get((row, column), None) or  # type: ignore
                        self.__alignment.get((row, -1), None) or
                        self.__alignment.get((-1, column), None) or
                        self.__alignment.get((-1, -1), None) or
                        '<'
                )

                cell: TableCell = self.__core[row, column]

                if (cell.kind == kind) and (cell.alignment == alignment or not cell.value):
                    continue

                if cell is self.__core.default:
                    self.__core[row, column] = TableCell(kind=kind, value=cell.value, alignment=alignment)
                else:
                    self.__core[row, column].alignment = alignment
                    self.__core[row, column].kind = kind

        self.__clean = True

    def __delitem__(self, cell: typing.Tuple[int, int]) -> None:
        """Remove a single cell from the table (set it to default)."""
        del self.__core[cell]

    def __getitem__(self, cell: typing.Tuple[int, int]) -> str:
        """Retrieve a value of a single cell in the table."""
        return self.__core[cell].value

    def __setitem__(self, cell: typing.Tuple[int, int], value: str) -> None:
        """Update a value of a single cell in the table."""
        self.__core[cell] = TableCell(kind=CELL, value=value)
        self.__clean = False


class SimpleTableWithAliases(SimpleTable):
    """
    Extended version of the :class:`~SimpleTable` which allows columns to have aliases.

    :param aliases: Aliases for the columns in the table.

                    If at least a single alias is provided as tuple of alias and verbose name, or the whole aliases
                    value is a mapping - first row with verbose values would be added automatically to the table. In
                    case some column doesn't have a verbose name - its alias would be displayed.
    :param heading_rows: How many rows should be used as a headings.
    :param heading_columns: How many columns should be used as a headings.
    """

    __slots__ = ('__aliases',)

    def __init__(
            self,
            aliases: typing.Union[typing.Iterable[typing.Union[str, typing.Tuple[str, str]]], typing.Mapping[str, str]],
            heading_rows: int = 0,
            heading_columns: int = 0,
    ) -> None:
        """Initialize new :class:`~SimpleTableWithAliases` instance."""
        super().__init__(heading_rows=heading_rows, heading_columns=heading_columns)

        column_aliases: typing.List[str] = []
        column_titles: typing.List[str] = []
        column_titles_ready: bool = False

        if isinstance(aliases, typing.Mapping):
            raw_aliases: typing.Tuple[str, ...]
            raw_titles: typing.Tuple[str, ...]
            raw_aliases, raw_titles = zip(*aliases.items())

            column_aliases.extend(map(str, raw_aliases))
            column_titles.extend(map(str, raw_titles))
            column_titles_ready = True

        else:
            item: typing.Union[str, typing.Tuple[str, str]]
            for item in aliases:
                if isinstance(item, str):
                    column_aliases.append(item)
                    column_titles.append(item)
                else:
                    alias: str
                    title: str
                    alias, title = item
                    column_aliases.append(str(alias))
                    column_titles.append(str(title))
                    column_titles_ready = True

        self.__aliases: 'typing_extensions.Final[typing.List[str]]' = column_aliases
        if column_titles_ready:
            super().append_row(column_titles)

    def align_cell(self, row: int, column: typing.Union[int, str], alignment: 'Alignment') -> None:
        """Align a single cell in the table."""
        if isinstance(column, str):
            column = self.__aliases.index(column)
        super().align_cell(row=row, column=column, alignment=alignment)

    def align_column(self, column: typing.Union[int, str], alignment: 'Alignment') -> None:
        """Align each cell in a single column of the table."""
        if isinstance(column, str):
            column = self.__aliases.index(column)
        super().align_column(column=column, alignment=alignment)

    def append_row(
            self,
            values: typing.Union[typing.Iterable[typing.Any], typing.Mapping[str, typing.Any]],
            *,
            strict: bool = False,
    ) -> None:
        """Append new row to the bottom of this table."""
        if isinstance(values, typing.Mapping):
            old_values: typing.Dict[str, typing.Any] = dict(values)
            values = [old_values.pop(alias, None) for alias in self.__aliases]
            if strict and old_values:
                raise ValueError(f'unexpected values: {list(old_values)}')

        super().append_row(values)

    def remove_column(self, column: typing.Union[int, str]) -> None:
        """Remove a single column from the table."""
        if isinstance(column, str):
            column = self.__aliases.index(column)
        super().remove_column(column)

    def __normalize_cell_index(self, cell: typing.Tuple[int, typing.Union[int, str]]) -> typing.Tuple[int, int]:
        """Normalize value of a cell index."""
        row: int
        column: typing.Union[int, str]
        row, column = cell
        if isinstance(column, str):
            column = self.__aliases.index(column)
        return row, column

    def __delitem__(self, cell: typing.Tuple[int, typing.Union[int, str]]) -> None:
        """Remove a single cell from the table (set it to default)."""
        super().__delitem__(self.__normalize_cell_index(cell))

    def __getitem__(self, cell: typing.Tuple[int, typing.Union[int, str]]) -> str:
        """Retrieve a value of a single cell in the table."""
        return super().__getitem__(self.__normalize_cell_index(cell))

    def __setitem__(self, cell: typing.Tuple[int, typing.Union[int, str]], value: str) -> None:
        """Update a value of a single cell in the table."""
        super().__setitem__(self.__normalize_cell_index(cell), value)


SIMPLE: TableDesign = (
    TableDesign()
    .with_horizontal(HEADING, CELL, '-')
    .with_intersection(HEADING, HEADING, CELL, CELL, '-+-')
    .with_intersection(HEADING, HEADING, HEADING, CELL, '-+-')
    .with_vertical(HEADING, HEADING, ' | ')
    .with_vertical(HEADING, CELL, ' | ')
    .with_vertical(CELL, CELL, ' | ')
)
# PRETTY: TableDesign = (
#     TableDesign()
#     .with_border_style('─', ' │ ', ' ╭─', '─╮ ', '─╯ ', ' ╰─')
#     .with_cell_style(HEADING, '─', ' │ ', '─┼─')
#     .with_border_transition(HEADING, '─┬─', '─┤ ', '─┴─', ' ├─')
#     .with_cell_style(CELL, '─', ' │ ', '─┼─')
#     .with_border_transition(CELL, '─┬─', '─┤ ', '─┴─', ' ├─')
#     .with_horizontal(HEADING, CELL, '━')
#     .with_intersection(HEADING, EMPTY, CELL, EMPTY, '━┥ ')
#     .with_intersection(HEADING, CELL, EMPTY, EMPTY, '─┸─')
#     .with_intersection(HEADING, HEADING, CELL, CELL, '━┿━')
#     .with_intersection(HEADING, CELL, HEADING, CELL, '─╂─')
#     .with_intersection(HEADING, HEADING, HEADING, CELL, '─╆━')
#     .with_intersection(EMPTY, HEADING, EMPTY, CELL, ' ┝━')
#     .with_vertical(HEADING, CELL, ' ┃ ')
# )
