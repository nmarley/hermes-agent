"""Session state storage: SQLite schema, messages, sessions, leases, and recovery.

The store owns persistence. It may import host and config foundations, never the agent,
gateway, tools, or a surface.
"""
