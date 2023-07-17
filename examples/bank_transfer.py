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

    from_acct = "Alice"
    to_acct = "Bob"

    # when r1:
    @when(r1)  # when I have exclusive access to r1...
    def _():
        print(from_acct, "=", r1.accounts[from_acct].balance)

    # when r1:
    @when(r2)  # when I have exclusive access to r2...
    def _():
        print(to_acct, "=", r2.accounts[to_acct].balance)

    # when r1, r2:
    @when(r1, r2)
    def _():
        r1.accounts[from_acct].balance -= 100
        r2.accounts[to_acct].balance += 100

        @when()  # whenever
        def _():
            print(f"Transfer 100: {from_acct}->{to_acct}")

    # when r2:
    @when(r2)  # when I have exclusive access to r2...
    def _():
        # guaranteed to see the transfer
        print(to_acct, "=", r2.accounts[to_acct].balance)

    # when r1:
    @when(r1)
    def _():
        # guaranteed to see the transfer
        print(from_acct, "=", r1.accounts[from_acct].balance)


if __name__ == "__main__":
    _main()
    wait()
