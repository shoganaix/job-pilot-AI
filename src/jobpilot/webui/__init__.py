"""Local web UI to edit the master CV and the search preferences.

``jobpilot web`` starts a tiny stdlib HTTP server bound to ``127.0.0.1`` that
renders forms over ``config/master_cv.yaml`` and ``config/profile.yaml`` so the
user never has to hand-edit nested YAML. Every save is validated with the very
same parsers the CLI uses, and the previous file is kept as ``<file>.bak``.

No new dependencies: the server is ``http.server``, the HTML is built with
f-strings (same style as ``pipeline.report``) and the data layer is PyYAML.
"""
