"""Example demonstrating a bank transfer."""

from pyrona import Region, wait, when


class Account:
    """A simple bank account."""
    def __init__(self, balance: int):
        """Constructor."""
        self.balance = balance


def _main():
    # Synchronously set up two regions, each representing a bank
    # with one account each
    # Create two empty regions
    r1 = Region("Bank1")
    r2 = Region("Bank2")
    # To access the regions, they must be opened
    with (r1, r2):
        r1.accounts = {"Alice": Account(1000)}  # flow-based ownership
        r2.accounts = {"Bob": Account(42)}

    # now r1, r2 are closed
    r1.make_shareable()
    r2.make_shareable()

    name = "Alice"

    # when r1:
    @when(r1)  # when I have exclusive access to r1...
    def _():
        print("name: ", r1.accounts[name].balance)

    # when r1, r2:
    @when(r1, r2)
    def _():
        r1.accounts[name].balance -= 100
        r2.accounts["Bob"].balance += 100

        @when()  # whenever
        def _():
            print(f"Transfer 100: {name}->Bob")

    # when r2:
    @when(r2)  # when I have exclusive access to r2...
    def _():
        print(r2.accounts["Bob"].balance)  # guaranteed to see the transfer


if __name__ == "__main__":
    _main()
    wait()
