"""Phase 14.2 — Traefik configuration smoke.

We don't boot Traefik in CI (needs a real domain + ACME); instead we parse
the static + dynamic YAML files and assert the required structure exists.
This catches typos, missing entrypoints, broken router→service references,
and ACME misconfiguration before the file ever hits a production host.

The acceptance criteria from the M14.2 plan:
  - HTTP→HTTPS redirect rule present
  - ACME challenge configured (httpchallenge per ADR)
  - Two routers: api.<domain> -> backend, <domain> -> frontend
  - docker-compose.prod.yml references the right services + ports
"""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")


REPO_ROOT = Path(__file__).resolve().parents[2]
TRAEFIK_DIR = REPO_ROOT / "infra" / "traefik"
COMPOSE_PROD = REPO_ROOT / "docker-compose.prod.yml"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_static_config_has_entrypoints_and_acme():
    static = _load(TRAEFIK_DIR / "traefik.yml")
    entrypoints = static.get("entryPoints", {})
    assert "web" in entrypoints, "missing :80 entrypoint"
    assert "websecure" in entrypoints, "missing :443 entrypoint"
    # HTTP -> HTTPS redirect must live on the `web` entrypoint.
    redirect = (
        entrypoints["web"].get("http", {}).get("redirections", {}).get("entryPoint", {})
    )
    assert redirect.get("to") == "websecure", "missing :80 -> :443 redirect"
    assert redirect.get("scheme") == "https"

    cert_resolvers = static.get("certificatesResolvers", {})
    assert "letsencrypt" in cert_resolvers, "missing Let's Encrypt resolver"
    acme = cert_resolvers["letsencrypt"].get("acme", {})
    assert acme.get("email"), "ACME requires an email contact"
    assert "httpChallenge" in acme, "M14.2 ADR locked in httpChallenge"


def test_dynamic_config_has_api_and_frontend_routers():
    dynamic = _load(TRAEFIK_DIR / "dynamic.yml")
    http = dynamic.get("http", {})
    routers = http.get("routers", {})
    services = http.get("services", {})

    assert "api" in routers and "frontend" in routers, (
        "expected `api` and `frontend` routers in dynamic config"
    )
    api_router = routers["api"]
    fe_router = routers["frontend"]

    assert api_router["entryPoints"] == ["websecure"]
    assert "Host(`api." in api_router["rule"], "api router must match api.<domain>"
    assert api_router.get("tls", {}).get("certResolver") == "letsencrypt"

    assert fe_router["entryPoints"] == ["websecure"]
    assert "Host(" in fe_router["rule"], "frontend router needs a Host rule"
    assert fe_router.get("tls", {}).get("certResolver") == "letsencrypt"

    # Service references must resolve.
    for name in (api_router["service"], fe_router["service"]):
        assert name in services, f"router references missing service {name!r}"
    api_service = services[api_router["service"]]
    loadbalancer = api_service.get("loadBalancer", {})
    assert any(
        "8002" in s.get("url", "") for s in loadbalancer.get("servers", [])
    ), "api service must target backend port 8002"


def test_compose_prod_has_traefik_and_app_services():
    compose = _load(COMPOSE_PROD)
    services = compose.get("services", {})
    for required in ("traefik", "api", "web", "postgres"):
        assert required in services, f"docker-compose.prod.yml missing service {required!r}"

    api = services["api"]
    web = services["web"]
    # Both app services must carry Traefik labels so the dynamic provider
    # discovers them. We accept either Docker-provider labels or a file
    # provider — both should at least declare `traefik.enable=true`.
    api_labels = api.get("labels", []) or []
    web_labels = web.get("labels", []) or []
    assert any("traefik.enable=true" in str(l) for l in api_labels), (
        "api service missing traefik.enable=true label"
    )
    assert any("traefik.enable=true" in str(l) for l in web_labels), (
        "web service missing traefik.enable=true label"
    )
