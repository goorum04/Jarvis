"""
Ventas y pedidos de la tienda online de Nacho. Soporta Shopify y WooCommerce;
STORE_PLATFORM en el .env elige cuál (ver CONFIGURAR_JARVIS.md para crear
las credenciales de solo lectura).
"""
import logging
import os
from collections import Counter
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

logger = logging.getLogger(__name__)

WOO_SALE_STATUSES = {"processing", "completed", "on-hold"}
MAX_PAGES = 20


class StoreNotConfigured(Exception):
    pass


def platform() -> str:
    return os.getenv("STORE_PLATFORM", "").lower()


def is_configured() -> bool:
    if platform() == "shopify":
        return bool(os.getenv("SHOPIFY_SHOP") and os.getenv("SHOPIFY_ACCESS_TOKEN"))
    if platform() == "woocommerce":
        return bool(os.getenv("WOO_URL") and os.getenv("WOO_CONSUMER_KEY") and os.getenv("WOO_CONSUMER_SECRET"))
    return False


def period_range(period: str, timezone: str) -> tuple[datetime, datetime]:
    tz = ZoneInfo(timezone)
    now = datetime.now(tz)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "yesterday":
        return today - timedelta(days=1), today
    if period == "week":
        return today - timedelta(days=6), now
    if period == "month":
        return today.replace(day=1), now
    return today, now


# ── Normalización: cada plataforma devuelve pedidos con esta forma ──
# {"number", "customer", "total", "currency", "created", "items": [(nombre, unidades)], "is_sale"}

def _woo_orders(params: dict) -> list[dict]:
    base = os.getenv("WOO_URL", "").rstrip("/")
    auth = (os.getenv("WOO_CONSUMER_KEY", ""), os.getenv("WOO_CONSUMER_SECRET", ""))
    orders, page = [], 1
    while page <= MAX_PAGES:
        response = httpx.get(
            f"{base}/wp-json/wc/v3/orders", params={**params, "per_page": 100, "page": page}, auth=auth, timeout=20
        )
        response.raise_for_status()
        for o in response.json():
            billing = o.get("billing") or {}
            orders.append({
                "number": o.get("number"),
                "customer": f"{billing.get('first_name', '')} {billing.get('last_name', '')}".strip(),
                "total": float(o.get("total") or 0),
                "currency": o.get("currency", ""),
                "created": o.get("date_created"),
                "items": [(i.get("name"), int(i.get("quantity") or 0)) for i in o.get("line_items", [])],
                "is_sale": o.get("status") in WOO_SALE_STATUSES,
            })
        if page >= int(response.headers.get("X-WP-TotalPages", "1")):
            break
        page += 1
    return orders


def _shopify_orders(params: dict) -> list[dict]:
    shop = os.getenv("SHOPIFY_SHOP", "").replace("https://", "").rstrip("/")
    version = os.getenv("SHOPIFY_API_VERSION", "2025-07")
    headers = {"X-Shopify-Access-Token": os.getenv("SHOPIFY_ACCESS_TOKEN", "")}
    url = f"https://{shop}/admin/api/{version}/orders.json"
    query = {**params, "limit": 250}
    orders = []
    for _ in range(MAX_PAGES):
        response = httpx.get(url, params=query, headers=headers, timeout=20)
        response.raise_for_status()
        for o in response.json().get("orders", []):
            customer = o.get("customer") or {}
            orders.append({
                "number": o.get("name"),
                "customer": f"{customer.get('first_name') or ''} {customer.get('last_name') or ''}".strip(),
                "total": float(o.get("total_price") or 0),
                "currency": o.get("currency", ""),
                "created": o.get("created_at"),
                "items": [(i.get("title"), int(i.get("quantity") or 0)) for i in o.get("line_items", [])],
                "is_sale": not o.get("cancelled_at") and o.get("financial_status") not in ("voided", "refunded"),
            })
        next_link = response.links.get("next", {}).get("url")
        if not next_link:
            break
        # En Shopify, la siguiente página solo admite page_info y limit.
        url, query = next_link, {}
    return orders


def _orders_between(start: datetime, end: datetime) -> list[dict]:
    if platform() == "shopify":
        return _shopify_orders({"status": "any", "created_at_min": start.isoformat(), "created_at_max": end.isoformat()})
    if platform() == "woocommerce":
        return _woo_orders({"after": start.isoformat(), "before": end.isoformat()})
    raise StoreNotConfigured("La tienda todavía no está conectada.")


def _check():
    if not is_configured():
        raise StoreNotConfigured("La tienda todavía no está conectada.")


def sales_summary(period: str, timezone: str) -> dict:
    _check()
    start, end = period_range(period, timezone)
    sales = [o for o in _orders_between(start, end) if o["is_sale"]]
    revenue = round(sum(o["total"] for o in sales), 2)
    return {
        "period": period,
        "orders": len(sales),
        "revenue": revenue,
        "currency": sales[0]["currency"] if sales else "",
        "average_order": round(revenue / len(sales), 2) if sales else 0,
    }


def top_products(period: str, timezone: str, limit: int = 5) -> dict:
    _check()
    start, end = period_range(period, timezone)
    units = Counter()
    for order in _orders_between(start, end):
        if order["is_sale"]:
            for name, quantity in order["items"]:
                units[name] += quantity
    return {"period": period, "products": [{"name": n, "units": u} for n, u in units.most_common(limit)]}


def pending_orders(limit: int = 5) -> dict:
    """Pedidos pagados y sin enviar, los más antiguos primero."""
    _check()
    if platform() == "shopify":
        orders = _shopify_orders({"status": "open", "financial_status": "paid", "fulfillment_status": "unfulfilled"})
    else:
        orders = _woo_orders({"status": "processing"})
    orders.sort(key=lambda o: o["created"] or "")
    return {
        "count": len(orders),
        "oldest": [{k: o[k] for k in ("number", "customer", "total", "currency", "created")} for o in orders[:limit]],
    }
