# This file makes the routers directory a Python package
# Import all routers here for easy access

from . import auth
from . import contacts
from . import debts

__all__ = ["auth", "contacts", "debts"]