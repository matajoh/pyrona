"""Example showing merge sort using BoC."""

import random
from time import sleep

from pyrona import Region, wait, when


Threshold = 10


def _sort_section(source: tuple, start: int, end: int, output: Region):
    if end < start:
        return

    if end - start + 1 <= Threshold:
        print("sorting", start, end)
        # below a threshold, we use the built-in sort function
        values = list(sorted(source[start:end + 1]))

        # when output:
        @when(output)
        def _():
            print("copying", start, end)
            # we add a random sleep to make the concurrency a bit
            # more interesting
            sleep(random.random() / 10)
            output.values[start:end + 1] = values

        return

    mid = (start + end) // 2
    _sort_section(source, start, mid, output)
    _sort_section(source, mid + 1, end, output)

    # when output:
    @when(output)
    def _():
        print("merging", start, end)
        # we add a random sleep to make the concurrency a bit
        # more interesting
        sleep(random.random() / 10)

        # merge in place
        i = start
        j = mid + 1
        k = mid

        if output.values[k] <= output.values[j]:
            return

        while i <= k and j <= end:
            if output.values[i] <= output.values[j]:
                i += 1
            else:
                value = output.values[j]
                index = j

                while index != i:
                    output.values[index] = output.values[index - 1]
                    index -= 1

                output.values[i] = value

                i += 1
                j += 1
                k += 1


def _main():
    # Create a region to hold the output
    r = Region("MergeSort")

    # Create an immutable list of integers as input
    values = tuple([random.randint(0, 100) for _ in range(100)])
    print("unsorted:", values)

    # Synchronously set up the region
    with r:
        r.values = [0] * len(values)

    r.make_shareable()

    # Sort the list
    _sort_section(values, 0, len(values) - 1, r)

    # when r:
    @when(r)
    def _():
        print("sorted:", r.values)


if __name__ == "__main__":
    _main()
    wait()
