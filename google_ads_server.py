"""Google Ads MCP Server — gRPC client implementation."""

from typing import Optional
from pydantic import Field
import os
import json
import logging
from pathlib import Path

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("google_ads_server")

mcp = FastMCP(
    "google-ads-server",
    dependencies=["google-ads", "google-auth-oauthlib", "python-dotenv"],
)

SCOPES = ["https://www.googleapis.com/auth/adwords"]

try:
    from dotenv import load_dotenv
    load_dotenv()
    logger.info("Environment variables loaded from .env file")
except ImportError:
    pass

GOOGLE_ADS_CREDENTIALS_PATH = os.environ.get("GOOGLE_ADS_CREDENTIALS_PATH")
GOOGLE_ADS_DEVELOPER_TOKEN = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN")
GOOGLE_ADS_LOGIN_CUSTOMER_ID = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")


def format_customer_id(customer_id: str) -> str:
    """Strip non-digits and zero-pad to 10 chars."""
    return "".join(c for c in str(customer_id) if c.isdigit()).zfill(10)


def _get_oauth_credentials() -> Credentials:
    """Load or create OAuth credentials, refreshing as needed."""
    if not GOOGLE_ADS_CREDENTIALS_PATH:
        raise ValueError("GOOGLE_ADS_CREDENTIALS_PATH environment variable not set")

    token_path = GOOGLE_ADS_CREDENTIALS_PATH
    creds = None
    client_config = None

    if os.path.exists(token_path):
        with open(token_path, "r") as f:
            data = json.load(f)
        if "installed" in data or "web" in data:
            client_config = data
        else:
            creds = Credentials.from_authorized_user_info(data, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                creds = None

        if not creds:
            if not client_config:
                client_id = os.environ.get("GOOGLE_ADS_CLIENT_ID")
                client_secret = os.environ.get("GOOGLE_ADS_CLIENT_SECRET")
                if not client_id or not client_secret:
                    raise ValueError(
                        "GOOGLE_ADS_CLIENT_ID and GOOGLE_ADS_CLIENT_SECRET required"
                    )
                client_config = {
                    "installed": {
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
                    }
                }
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(port=0)

        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return creds


def _build_client() -> GoogleAdsClient:
    """Build a GoogleAdsClient using saved OAuth credentials."""
    creds = _get_oauth_credentials()
    config = {
        "developer_token": GOOGLE_ADS_DEVELOPER_TOKEN,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "refresh_token": creds.refresh_token,
        "use_proto_plus": True,
    }
    if GOOGLE_ADS_LOGIN_CUSTOMER_ID:
        config["login_customer_id"] = format_customer_id(GOOGLE_ADS_LOGIN_CUSTOMER_ID)
    return GoogleAdsClient.load_from_dict(config)


def _run_query(customer_id: str, query: str) -> list:
    """Execute a GAQL query and return rows as dicts."""
    client = _build_client()
    service = client.get_service("GoogleAdsService")
    cid = format_customer_id(customer_id)
    response = service.search(customer_id=cid, query=query)

    rows = []
    for row in response:
        rows.append(row)
    return rows


def _format_micros(micros: int) -> str:
    """Convert micros to currency string."""
    return f"${micros / 1_000_000:,.2f}"


def _safe_attr(obj: object, *attrs: str) -> str:
    """Safely traverse nested proto attributes."""
    current = obj
    for attr in attrs:
        current = getattr(current, attr, None)
        if current is None:
            return "N/A"
    return str(current)


# ── Tools ──────────────────────────────────────────────────────────────────


@mcp.tool()
async def list_accounts() -> str:
    """List all accessible Google Ads accounts under the MCC.

    Returns account IDs, names, currency, timezone, and status.
    This is the first command to run — use the returned IDs for all other tools.
    """
    try:
        client = _build_client()

        # Step 1: list accessible customer resource names
        customer_service = client.get_service("CustomerService")
        accessible = customer_service.list_accessible_customers()
        resource_names = accessible.resource_names

        lines = ["Accessible Google Ads Accounts:", "-" * 70]

        # Step 2: for each MCC, list child accounts with details
        ga_service = client.get_service("GoogleAdsService")
        login_cid = format_customer_id(GOOGLE_ADS_LOGIN_CUSTOMER_ID)

        query = """
            SELECT
                customer_client.id,
                customer_client.descriptive_name,
                customer_client.currency_code,
                customer_client.time_zone,
                customer_client.status,
                customer_client.manager
            FROM customer_client
        """
        try:
            rows = _run_query(login_cid, query)
            for row in rows:
                cc = row.customer_client
                role = "MCC" if cc.manager else "Account"
                lines.append(
                    f"  [{role}] {cc.id} — {cc.descriptive_name} "
                    f"({cc.currency_code}, {cc.time_zone}, {cc.status.name})"
                )
        except GoogleAdsException:
            # Fallback: just list resource names
            for rn in resource_names:
                cid = rn.split("/")[-1]
                lines.append(f"  Account ID: {cid}")

        return "\n".join(lines)
    except Exception as e:
        return f"Error listing accounts: {e}"


@mcp.tool()
async def execute_gaql_query(
    customer_id: str = Field(description="Google Ads customer ID (10 digits, no dashes)"),
    query: str = Field(description="Valid GAQL query string"),
    format: str = Field(default="table", description="Output format: 'table', 'json', or 'csv'"),
) -> str:
    """Execute any GAQL query with flexible output formatting.

    Args:
        customer_id: Google Ads customer ID (10 digits, no dashes)
        query: GAQL query to execute
        format: Output format — 'table' (default), 'json', or 'csv'

    Example queries:
        SELECT campaign.name, metrics.clicks FROM campaign WHERE segments.date DURING LAST_7_DAYS
        SELECT keyword.text, metrics.ctr FROM keyword_view ORDER BY metrics.impressions DESC LIMIT 20
    """
    try:
        client = _build_client()
        service = client.get_service("GoogleAdsService")
        cid = format_customer_id(customer_id)

        response = service.search(customer_id=cid, query=query)

        # Convert proto rows to dicts
        results = []
        for row in response:
            results.append(type(row).to_dict(row))

        if not results:
            return "No results found."

        if format.lower() == "json":
            return json.dumps(results, indent=2, default=str)

        # Flatten nested dicts for table/csv
        flat_rows = []
        for row in results:
            flat = {}
            for key, val in row.items():
                if isinstance(val, dict):
                    for subkey, subval in val.items():
                        if isinstance(subval, dict):
                            for k3, v3 in subval.items():
                                flat[f"{key}.{subkey}.{k3}"] = str(v3) if v3 is not None else ""
                        else:
                            flat[f"{key}.{subkey}"] = str(subval) if subval is not None else ""
                else:
                    flat[key] = str(val) if val is not None else ""
            flat_rows.append(flat)

        # Remove empty columns
        all_keys = list(flat_rows[0].keys())
        active_keys = [k for k in all_keys if any(r.get(k, "") not in ("", "0", "None", "0.0") for r in flat_rows)]
        if not active_keys:
            active_keys = all_keys

        if format.lower() == "csv":
            lines = [",".join(active_keys)]
            for row in flat_rows:
                lines.append(",".join(row.get(k, "").replace(",", ";") for k in active_keys))
            return "\n".join(lines)

        # Table format
        widths = {k: len(k) for k in active_keys}
        for row in flat_rows:
            for k in active_keys:
                widths[k] = max(widths[k], len(row.get(k, "")))

        header = " | ".join(f"{k:{widths[k]}}" for k in active_keys)
        sep = "-" * len(header)
        lines = [f"Results ({len(flat_rows)} rows):", sep, header, sep]
        for row in flat_rows:
            lines.append(" | ".join(f"{row.get(k, ''):{widths[k]}}" for k in active_keys))
        return "\n".join(lines)

    except GoogleAdsException as ex:
        errors = [e.message for e in ex.failure.errors]
        return f"GAQL error: {'; '.join(errors)}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def get_campaign_performance(
    customer_id: str = Field(description="Google Ads customer ID (10 digits, no dashes)"),
    days: int = Field(default=30, description="Lookback period in days (7, 14, 30, 90)"),
) -> str:
    """Get campaign performance metrics.

    Returns campaign name, status, impressions, clicks, cost, conversions, and avg CPC.
    Cost values are in the account's currency (check with list_accounts).
    """
    date_map = {7: "LAST_7_DAYS", 14: "LAST_14_DAYS", 30: "LAST_30_DAYS", 90: "LAST_90_DAYS"}
    date_range = date_map.get(days, "LAST_30_DAYS")

    query = f"""
        SELECT
            campaign.id,
            campaign.name,
            campaign.status,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.average_cpc
        FROM campaign
        WHERE segments.date DURING {date_range}
        ORDER BY metrics.cost_micros DESC
        LIMIT 50
    """
    try:
        rows = _run_query(customer_id, query)
        if not rows:
            return "No campaign data found."

        lines = [f"Campaign Performance (last {days} days):", "=" * 100]
        for row in rows:
            c = row.campaign
            m = row.metrics
            ctr = (m.clicks / m.impressions * 100) if m.impressions > 0 else 0
            lines.append(
                f"  {c.name} [{c.status.name}]\n"
                f"    Impressions: {m.impressions:,} | Clicks: {m.clicks:,} | "
                f"CTR: {ctr:.1f}% | Cost: {_format_micros(m.cost_micros)} | "
                f"Conversions: {m.conversions:.1f} | Avg CPC: {_format_micros(m.average_cpc)}"
            )
        return "\n".join(lines)

    except GoogleAdsException as ex:
        errors = [e.message for e in ex.failure.errors]
        return f"Error: {'; '.join(errors)}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def get_ad_performance(
    customer_id: str = Field(description="Google Ads customer ID (10 digits, no dashes)"),
    days: int = Field(default=30, description="Lookback period in days (7, 14, 30, 90)"),
) -> str:
    """Get ad-level performance metrics.

    Returns ad ID, campaign, ad group, impressions, clicks, cost, and conversions.
    """
    date_map = {7: "LAST_7_DAYS", 14: "LAST_14_DAYS", 30: "LAST_30_DAYS", 90: "LAST_90_DAYS"}
    date_range = date_map.get(days, "LAST_30_DAYS")

    query = f"""
        SELECT
            ad_group_ad.ad.id,
            ad_group_ad.ad.name,
            ad_group_ad.status,
            campaign.name,
            ad_group.name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions
        FROM ad_group_ad
        WHERE segments.date DURING {date_range}
        ORDER BY metrics.impressions DESC
        LIMIT 50
    """
    try:
        rows = _run_query(customer_id, query)
        if not rows:
            return "No ad performance data found."

        lines = [f"Ad Performance (last {days} days):", "=" * 100]
        for row in rows:
            ad = row.ad_group_ad
            m = row.metrics
            lines.append(
                f"  Ad {ad.ad.id} [{ad.status.name}]\n"
                f"    Campaign: {row.campaign.name} > {row.ad_group.name}\n"
                f"    Impressions: {m.impressions:,} | Clicks: {m.clicks:,} | "
                f"Cost: {_format_micros(m.cost_micros)} | Conversions: {m.conversions:.1f}"
            )
        return "\n".join(lines)

    except GoogleAdsException as ex:
        errors = [e.message for e in ex.failure.errors]
        return f"Error: {'; '.join(errors)}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def get_ad_creatives(
    customer_id: str = Field(description="Google Ads customer ID (10 digits, no dashes)"),
) -> str:
    """Get ad creative details — headlines, descriptions, and URLs.

    Useful for creative audits and ad copy review.
    """
    query = """
        SELECT
            ad_group_ad.ad.id,
            ad_group_ad.ad.name,
            ad_group_ad.ad.type,
            ad_group_ad.ad.final_urls,
            ad_group_ad.status,
            ad_group_ad.ad.responsive_search_ad.headlines,
            ad_group_ad.ad.responsive_search_ad.descriptions,
            ad_group.name,
            campaign.name
        FROM ad_group_ad
        WHERE ad_group_ad.status != 'REMOVED'
        ORDER BY campaign.name, ad_group.name
        LIMIT 50
    """
    try:
        rows = _run_query(customer_id, query)
        if not rows:
            return "No ad creatives found."

        lines = [f"Ad Creatives:", "=" * 80]
        for i, row in enumerate(rows, 1):
            ad = row.ad_group_ad.ad
            lines.append(f"\n{i}. Campaign: {row.campaign.name}")
            lines.append(f"   Ad Group: {row.ad_group.name}")
            lines.append(f"   Ad ID: {ad.id} | Status: {row.ad_group_ad.status.name} | Type: {ad.type_.name}")

            rsa = ad.responsive_search_ad
            if rsa and rsa.headlines:
                lines.append("   Headlines:")
                for h in rsa.headlines:
                    pin = f" [pinned: {h.pinned_field.name}]" if h.pinned_field else ""
                    lines.append(f"     - {h.text}{pin}")
            if rsa and rsa.descriptions:
                lines.append("   Descriptions:")
                for d in rsa.descriptions:
                    pin = f" [pinned: {d.pinned_field.name}]" if d.pinned_field else ""
                    lines.append(f"     - {d.text}{pin}")

            if ad.final_urls:
                lines.append(f"   URLs: {', '.join(ad.final_urls)}")
            lines.append("-" * 80)
        return "\n".join(lines)

    except GoogleAdsException as ex:
        errors = [e.message for e in ex.failure.errors]
        return f"Error: {'; '.join(errors)}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def get_account_currency(
    customer_id: str = Field(description="Google Ads customer ID (10 digits, no dashes)"),
) -> str:
    """Get the account's currency code and timezone."""
    query = """
        SELECT customer.id, customer.descriptive_name, customer.currency_code, customer.time_zone
        FROM customer LIMIT 1
    """
    try:
        rows = _run_query(customer_id, query)
        if not rows:
            return "Account not found."
        c = rows[0].customer
        return f"Account {c.id} ({c.descriptive_name}): {c.currency_code}, {c.time_zone}"
    except GoogleAdsException as ex:
        errors = [e.message for e in ex.failure.errors]
        return f"Error: {'; '.join(errors)}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def get_keyword_performance(
    customer_id: str = Field(description="Google Ads customer ID (10 digits, no dashes)"),
    days: int = Field(default=30, description="Lookback period in days"),
) -> str:
    """Get keyword-level performance including quality score and search terms.

    Returns keyword text, match type, quality score, impressions, clicks, cost, conversions.
    """
    date_map = {7: "LAST_7_DAYS", 14: "LAST_14_DAYS", 30: "LAST_30_DAYS", 90: "LAST_90_DAYS"}
    date_range = date_map.get(days, "LAST_30_DAYS")

    query = f"""
        SELECT
            ad_group_criterion.keyword.text,
            ad_group_criterion.keyword.match_type,
            ad_group_criterion.quality_info.quality_score,
            campaign.name,
            ad_group.name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.ctr,
            metrics.average_cpc
        FROM keyword_view
        WHERE segments.date DURING {date_range}
        ORDER BY metrics.impressions DESC
        LIMIT 50
    """
    try:
        rows = _run_query(customer_id, query)
        if not rows:
            return "No keyword data found."

        lines = [f"Keyword Performance (last {days} days):", "=" * 100]
        for row in rows:
            kw = row.ad_group_criterion.keyword
            qs = row.ad_group_criterion.quality_info.quality_score
            m = row.metrics
            qs_str = str(qs) if qs else "N/A"
            lines.append(
                f"  \"{kw.text}\" [{kw.match_type.name}] QS:{qs_str}\n"
                f"    Campaign: {row.campaign.name} > {row.ad_group.name}\n"
                f"    Impressions: {m.impressions:,} | Clicks: {m.clicks:,} | "
                f"CTR: {m.ctr:.1%} | Cost: {_format_micros(m.cost_micros)} | "
                f"Conversions: {m.conversions:.1f} | Avg CPC: {_format_micros(m.average_cpc)}"
            )
        return "\n".join(lines)

    except GoogleAdsException as ex:
        errors = [e.message for e in ex.failure.errors]
        return f"Error: {'; '.join(errors)}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def get_search_terms(
    customer_id: str = Field(description="Google Ads customer ID (10 digits, no dashes)"),
    days: int = Field(default=30, description="Lookback period in days"),
) -> str:
    """Get search terms report — actual queries triggering your ads.

    Critical for finding wasted spend and negative keyword opportunities.
    """
    date_map = {7: "LAST_7_DAYS", 14: "LAST_14_DAYS", 30: "LAST_30_DAYS", 90: "LAST_90_DAYS"}
    date_range = date_map.get(days, "LAST_30_DAYS")

    query = f"""
        SELECT
            search_term_view.search_term,
            campaign.name,
            ad_group.name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions
        FROM search_term_view
        WHERE segments.date DURING {date_range}
        ORDER BY metrics.cost_micros DESC
        LIMIT 100
    """
    try:
        rows = _run_query(customer_id, query)
        if not rows:
            return "No search term data found."

        lines = [f"Search Terms (last {days} days, by spend):", "=" * 100]
        for row in rows:
            m = row.metrics
            ctr = (m.clicks / m.impressions * 100) if m.impressions > 0 else 0
            lines.append(
                f"  \"{row.search_term_view.search_term}\"\n"
                f"    Campaign: {row.campaign.name} > {row.ad_group.name}\n"
                f"    Impressions: {m.impressions:,} | Clicks: {m.clicks:,} | "
                f"CTR: {ctr:.1f}% | Cost: {_format_micros(m.cost_micros)} | "
                f"Conversions: {m.conversions:.1f}"
            )
        return "\n".join(lines)

    except GoogleAdsException as ex:
        errors = [e.message for e in ex.failure.errors]
        return f"Error: {'; '.join(errors)}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def get_image_assets(
    customer_id: str = Field(description="Google Ads customer ID (10 digits, no dashes)"),
    limit: int = Field(default=50, description="Max image assets to return"),
) -> str:
    """List image assets with URLs and dimensions."""
    query = f"""
        SELECT
            asset.id, asset.name, asset.type,
            asset.image_asset.full_size.url,
            asset.image_asset.full_size.height_pixels,
            asset.image_asset.full_size.width_pixels,
            asset.image_asset.file_size
        FROM asset
        WHERE asset.type = 'IMAGE'
        LIMIT {limit}
    """
    try:
        rows = _run_query(customer_id, query)
        if not rows:
            return "No image assets found."

        lines = ["Image Assets:", "=" * 80]
        for i, row in enumerate(rows, 1):
            a = row.asset
            img = a.image_asset.full_size
            size_kb = (a.image_asset.file_size / 1024) if a.image_asset.file_size else 0
            lines.append(
                f"  {i}. ID: {a.id} | {a.name}\n"
                f"     {img.width_pixels}x{img.height_pixels} | {size_kb:.1f} KB\n"
                f"     URL: {img.url}"
            )
        return "\n".join(lines)

    except GoogleAdsException as ex:
        errors = [e.message for e in ex.failure.errors]
        return f"Error: {'; '.join(errors)}"
    except Exception as e:
        return f"Error: {e}"


# ── Resources & Prompts ────────────────────────────────────────────────────


@mcp.resource("gaql://reference")
def gaql_reference() -> str:
    """GAQL quick reference."""
    return """
# Google Ads Query Language (GAQL) Reference

## Structure
    SELECT field1, field2 FROM resource WHERE condition ORDER BY field LIMIT n

## Common Resources
    campaign, ad_group, ad_group_ad, keyword_view, search_term_view, asset, campaign_asset

## Metric Fields
    metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions,
    metrics.ctr, metrics.average_cpc, metrics.conversions_value

## Date Ranges
    WHERE segments.date DURING LAST_7_DAYS / LAST_14_DAYS / LAST_30_DAYS / LAST_90_DAYS
    WHERE segments.date BETWEEN '2026-01-01' AND '2026-01-31'

## Tips
    - Cost in micros: 1,000,000 = $1.00
    - Always LIMIT results
    - Use list_accounts() first to get customer IDs
"""


@mcp.prompt("google_ads_workflow")
def google_ads_workflow() -> str:
    """Recommended workflow for Google Ads analysis."""
    return """
Workflow:
1. list_accounts() → get customer IDs
2. get_account_currency(customer_id) → confirm currency
3. get_campaign_performance(customer_id, days=30) → overview
4. get_keyword_performance(customer_id) → quality scores
5. get_search_terms(customer_id) → wasted spend / negative keyword opportunities
6. get_ad_creatives(customer_id) → creative audit
7. execute_gaql_query(customer_id, query) → custom analysis
"""


if __name__ == "__main__":
    mcp.run()
