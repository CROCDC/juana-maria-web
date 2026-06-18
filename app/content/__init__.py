"""Static, code-owned site content (the topic registry).

Topic *definitions* (slug, route, template, copy) live here because their
content and templates are part of the codebase. Only the mutable *visibility*
state (which topics are currently published) lives in the database, edited from
the admin panel. See ``app/content/topics.py``.
"""
