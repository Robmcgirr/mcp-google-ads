"""
Run GAQL queries for Tasks 6, 7, 8:
- Impression share data
- Hour-of-day performance
- Audience segments
"""
import json
from google.ads.googleads.client import GoogleAdsClient

CUSTOMER_ID = "1682033495"
LOGIN_CUSTOMER_ID = "8081286543"
DEV_TOKEN = "XoDTB2_BCNajdX8kx2zlRg"
CREDENTIALS_PATH = "/Users/bobbybot/Projects/mcp-google-ads/credentials.json"

def get_client():
    with open(CREDENTIALS_PATH) as f:
        creds = json.load(f)
    config = {
        "developer_token": DEV_TOKEN,
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "refresh_token": creds["refresh_token"],
        "login_customer_id": LOGIN_CUSTOMER_ID,
        "use_proto_plus": True,
    }
    return GoogleAdsClient.load_from_dict(config, version="v23")

def run_query(client, customer_id, query, label):
    ga_service = client.get_service("GoogleAdsService")
    print(f"\n{'='*60}")
    print(f"=== {label} ===")
    print(f"{'='*60}")
    try:
        response = ga_service.search(customer_id=customer_id, query=query)
        rows = list(response)
        if not rows:
            print("No results returned.")
            return
        for row in rows:
            print(row)
    except Exception as e:
        print(f"ERROR: {e}")

def main():
    client = get_client()

    # Task 6: Impression Share
    run_query(client, CUSTOMER_ID, """
        SELECT
            campaign.name,
            metrics.search_impression_share,
            metrics.search_top_impression_share,
            metrics.search_absolute_top_impression_share,
            metrics.search_budget_lost_impression_share,
            metrics.search_rank_lost_impression_share
        FROM campaign
        WHERE campaign.status = 'ENABLED'
            AND segments.date DURING LAST_30_DAYS
    """, "TASK 6: Impression Share (Last 30 Days)")

    # Task 7: Hour-of-Day Performance
    run_query(client, CUSTOMER_ID, """
        SELECT
            segments.hour,
            metrics.clicks,
            metrics.impressions,
            metrics.cost_micros,
            metrics.conversions
        FROM campaign
        WHERE campaign.status = 'ENABLED'
            AND segments.date DURING LAST_30_DAYS
    """, "TASK 7: Hour-of-Day Performance (Last 30 Days)")

    # Task 8: Audience Segments
    run_query(client, CUSTOMER_ID, """
        SELECT
            campaign_audience_view.resource_name
        FROM campaign_audience_view
    """, "TASK 8: Audience Segments")

if __name__ == "__main__":
    main()
