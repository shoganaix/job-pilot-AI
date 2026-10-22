"""Localhost HTTP server for the JobPilot editors.

Binds to ``127.0.0.1`` only and rejects any POST whose ``Host`` header is not
this server, so a page on another origin (or a DNS-rebinding attack) cannot
write the configs. No templates, no framework: ``forms.py`` renders, this file
routes and persists.
"""

from __future__ import annotations

import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from ..config import ConfigError
from . import forms, payload, yaml_io

MAX_BODY = 2 * 1024 * 1024  # 2 MiB is far more than any CV form posts
Form = dict[str, list[str]]


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    profile_path: Path
    master_cv_path: Path
    report_path: Path | None


class _Handler(BaseHTTPRequestHandler):
    server_version = "jobpilot-web"
    server: _Server  # narrowed attribute

    # ------------------------------------------------------------------ #
    # plumbing
    # ------------------------------------------------------------------ #
    def log_message(self, fmt: str, *args: Any) -> None:
        pass  # keep the terminal quiet; errors surface as error pages

    def _send(self, body: str, status: int = 200) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, location: str) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").strip().lower()
        allowed = ("127.0.0.1:", "localhost:", "[::1]:")
        return host.startswith(allowed) or host in ("127.0.0.1", "localhost", "[::1]")

    def _read_form(self) -> Form | None:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            self._send(forms.page("Demasiado", "<p>POST demasiado grande.</p>", "/",
                                  error="El formulario supera el límite de 2 MiB."), 413)
            return None
        raw = self.rfile.read(length).decode("utf-8", "replace") if length else ""
        return parse_qs(raw, keep_blank_values=True)

    # ------------------------------------------------------------------ #
    # GET
    # ------------------------------------------------------------------ #
    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)
        flash = "Guardado ✔" if "ok" in query else ""

        try:
            if path == "/":
                self._send(self._home(flash))
            elif path == "/cv":
                cv = yaml_io.load_yaml(self.server.master_cv_path)
                self._send(forms.cv_form(cv, flash=flash))
            elif path == "/prefs":
                self._send(self._prefs_page(flash))
            elif path == "/families":
                data = yaml_io.load_yaml(self.server.profile_path)
                self._send(forms.families_list(data.get("families", []) or [], flash=flash))
            elif path.startswith("/families/"):
                fam = self._family(path.removeprefix("/families/"))
                if fam is None:
                    self._send(forms.page(
                        "Familia", "<p>Familia no encontrada.</p>", "/families",
                        error="No existe esa familia en config/profile.yaml."), 404)
                else:
                    self._send(forms.family_form(fam, flash=flash))
            elif path == "/report":
                self._report()
            else:
                self._send(forms.page(
                    "404", "<p>Ruta no encontrada.</p>", "/",
                    error=f"No hay nada en {path}."), 404)
        except ConfigError as exc:
            self._send(forms.page("Error de configuración", "<p>No se pudo cargar.</p>",
                                  "/", error=str(exc)), 500)

    # ------------------------------------------------------------------ #
    # POST
    # ------------------------------------------------------------------ #
    def do_POST(self) -> None:  # noqa: N802
        path = unquote(urlparse(self.path).path)
        if not self._host_ok():
            self._send(forms.page("Prohibido", "<p>Host no permitido.</p>", "/",
                                  error="POST solo aceptado desde este servidor."), 403)
            return
        form = self._read_form()
        if form is None:
            return

        try:
            if path == "/cv":
                self._save_cv(form)
            elif path == "/prefs":
                self._save_prefs(form)
            elif path.startswith("/families/"):
                self._save_family(path.removeprefix("/families/"), form)
            else:
                self._send(forms.page("404", "<p>Ruta no encontrada.</p>", "/",
                                      error=f"No hay nada en {path}."), 404)
        except ConfigError as exc:
            self._send_error_form(path, str(exc))

    # ------------------------------------------------------------------ #
    # routes
    # ------------------------------------------------------------------ #
    def _home(self, flash: str) -> str:
        data = yaml_io.load_yaml(self.server.profile_path)
        return forms.home(
            str(self.server.master_cv_path),
            str(self.server.profile_path),
            len(data.get("families", []) or []),
            flash=flash,
        )

    def _prefs_page(self, flash: str = "", error: str = "",
                    prefill: dict[str, Any] | None = None) -> str:
        data = prefill if prefill is not None else yaml_io.load_yaml(
            self.server.profile_path
        )
        return forms.prefs_form(
            data.get("search", {}) or {},
            data.get("profile", {}) or {},
            data.get("ats_companies", {}) or {},
            flash=flash,
            error=error,
        )

    def _family(self, fam_id: str) -> dict[str, Any] | None:
        data = yaml_io.load_yaml(self.server.profile_path)
        for fam in data.get("families", []) or []:
            if str(fam.get("id", "")) == fam_id:
                return dict(fam)
        return None

    def _report(self) -> None:
        path = self.server.report_path
        if path is None or not path.exists():
            self._send(forms.page(
                "Report", "<p>Aún no hay report.</p>", "/",
                error="Genera uno con `jobpilot report`."), 404)
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ------------------------------------------------------------------ #
    # saves
    # ------------------------------------------------------------------ #
    def _save_cv(self, form: Form) -> None:
        path = self.server.master_cv_path
        try:
            payload_data = payload.build_master_cv(form)
            yaml_io.validate_master_cv(payload_data)
        except ConfigError as exc:
            self._send(forms.cv_form(_cv_from_form(form), error=f"No se guardó: {exc}"), 400)
            return
        yaml_io.save_yaml(path, payload_data)
        self._redirect("/cv?ok=1")

    def _save_prefs(self, form: Form) -> None:
        path = self.server.profile_path
        original = yaml_io.load_yaml(path)
        try:
            patch = payload.build_profile_patch(form)
        except ConfigError as exc:
            self._send(self._prefs_page(error=f"No se guardó: {exc}",
                                        prefill=original), 400)
            return
        merged = payload.apply_profile_patch(original, patch)
        try:
            yaml_io.validate_profile(merged)
        except ConfigError as exc:
            prefill = dict(original)
            prefill.update(patch)
            self._send(self._prefs_page(error=f"No se guardó: {exc}",
                                        prefill=prefill), 400)
            return
        yaml_io.save_yaml(path, merged)
        self._redirect("/prefs?ok=1")

    def _save_family(self, fam_id: str, form: Form) -> None:
        path = self.server.profile_path
        original = yaml_io.load_yaml(path)
        families = list(original.get("families", []) or [])
        existing = next(
            (f for f in families if str(f.get("id", "")) == fam_id), None
        )
        if existing is None:
            self._send(forms.page(
                "Familia", "<p>No encontrada.</p>", "/families",
                error="No existe esa familia."), 404)
            return
        try:
            updated = payload.build_family(form, existing)
        except ConfigError as exc:
            self._send(forms.family_form(dict(existing),
                                         error=f"No se guardó: {exc}"), 400)
            return

        families[families.index(existing)] = updated
        merged = dict(original)
        merged["families"] = families
        try:
            yaml_io.validate_profile(merged)
        except ConfigError as exc:
            self._send(forms.family_form(updated, error=f"No se guardó: {exc}"), 400)
            return
        yaml_io.save_yaml(path, merged)
        self._redirect(f"/families/{fam_id}?ok=1")

    def _send_error_form(self, path: str, message: str) -> None:
        """A ConfigError escaped the save helper: show it without losing state."""
        if path == "/cv":
            self._send(forms.page("Mi CV", "<p>No se guardó.</p>", "/cv",
                                  error=message), 400)
        elif path == "/prefs":
            self._send(self._prefs_page(error=message), 400)
        else:
            self._send(forms.page("Familias", "<p>No se guardó.</p>", "/families",
                                  error=message), 400)


def _cv_from_form(form: Form) -> dict[str, Any]:
    """Best-effort CV for re-rendering after a validation error."""
    try:
        return payload.build_master_cv(form)
    except ConfigError:
        return {}


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def make_server(
    profile_path: Path,
    master_cv_path: Path,
    *,
    port: int = 8765,
    report_path: Path | None = None,
) -> _Server:
    """Build (but do not start) a server bound to 127.0.0.1."""
    httpd = _Server(("127.0.0.1", port), _Handler)
    httpd.profile_path = profile_path
    httpd.master_cv_path = master_cv_path
    httpd.report_path = report_path
    return httpd


def serve(
    profile_path: Path,
    master_cv_path: Path,
    *,
    port: int = 8765,
    report_path: Path | None = None,
    open_browser: bool = False,
) -> int:
    httpd = make_server(
        profile_path, master_cv_path, port=port, report_path=report_path
    )
    host = str(httpd.server_address[0])
    port_bound = int(httpd.server_address[1])
    url = f"http://{host}:{port_bound}/"
    print(f"JobPilot web UI en {url}  (Ctrl+C para parar)")
    print(f"  CV:       {master_cv_path}")
    print(f"  Perfil:   {profile_path}")
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nparado.")
    finally:
        httpd.server_close()
    return 0
