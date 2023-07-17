"""Example showing merge sort using BoC."""

import random

from pyrona import Region, wait, when


Threshold = 10


def _sort_section(source: tuple, start: int, end: int, output: Region):
    if end < start:
        return

    if end - start + 1 <= Threshold:
        # when output:
        @when(output)
        def _():
            print("sorting", start, end)
            output.values = list(sorted(source[start:end + 1]))

        return

    lhs = Region("lhs").make_shareable()
    rhs = Region("rhs").make_shareable()
    mid = (start + end) // 2
    _sort_section(source, start, mid, lhs)
    _sort_section(source, mid + 1, end, rhs)

    # when output:
    @when(output, lhs, rhs)
    def _():
        print("merging", start, end)

        i = 0
        j = 0
        values = []
        while i < len(lhs.values) and j < len(rhs.values):
            if lhs.values[i] < rhs.values[j]:
                values.append(lhs.values[i])
                i += 1
            else:
                values.append(rhs.values[j])
                j += 1

        while i < len(lhs.values):
            values.append(lhs.values[i])
            i += 1

        while j < len(rhs.values):
            values.append(rhs.values[j])
            j += 1

        output.values = values


def _main():
    # Create an immutable list of integers as input
    values = tuple([random.randint(0, 100) for _ in range(100)])
    print("unsorted:", values)

    # Create a region to hold the output
    output = Region("MergeSort").make_shareable()

    # Sort the list
    _sort_section(values, 0, len(values) - 1, output)

    # when r:
    @when(output)
    def _():
        print("sorted:", output.values)


if __name__ == "__main__":
    _main()
    wait()
