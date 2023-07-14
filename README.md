# pyrona
This repo contains an exploration of the ideas put forth in
[The FrankenPEP for Venice and BoC](https://github.com/TobiasWrigstad/peps/blob/pyrona/pep-9999.rst)
which proposes a Behavior-oriented Concurrency runtime for Python. Please refer
to the PEP for details on the theory and concepts demonstrated here.

## Getting Started

We suggest you begin by cloning the repository and then creating a virtual
environment into which to instal the package and its dependencies. For Linux,
that will look something like this:

    python3 -m venv .env
    . .env/bin/activate
    pip install -e .[test,examples]

and, in Windows:

    python -m venv .env
    .env\Scripts\activate
    pip install -e .[test,examples]

From that point, you can run the tests by invoking `pytest` at the root of the
project. We also include an [example program](examples/index_comparison.py) which
demonstrates a simple use case for the runtime.
