"""Make the project root importable so tests can `import tools`, `import agent`."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
