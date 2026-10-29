"""Outbound webhook URL checks (SSRF guard).

SafeData posts disposal notices to the address saved on a connected system. That address
must be a public http(s) URL: never localhost, a private network, or a cloud metadata address.
"""
import ipaddress
import socket
from urllib.parse import urlparse


def _blocked_ip(ip: str) -> bool:
    a = ipaddress.ip_address(ip)
    return (a.is_private or a.is_loopback or a.is_link_local or a.is_reserved
            or a.is_multicast or a.is_unspecified)


def url_problem(url: str, resolve: bool = False) -> str | None:
    """Return a plain-language problem with the URL, or None if it is acceptable."""
    u = (url or "").strip()
    if not u:
        return None
    try:
        parsed = urlparse(u)
    except ValueError:
        return "The address is not a valid URL."
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return "Use a full http:// or https:// address."
    if parsed.username or parsed.password:
        return "Do not put a user name or password in the address."
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        return "Internal addresses are not allowed."
    try:
        if _blocked_ip(host):
            return "Internal addresses are not allowed."
        return None  # a public IP literal
    except ValueError:
        pass  # a name, not an IP literal
    if resolve:
        try:
            for info in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80)):
                if _blocked_ip(info[4][0]):
                    return "The address points to an internal network."
        except socket.gaierror:
            return "The address could not be resolved."
    return None
