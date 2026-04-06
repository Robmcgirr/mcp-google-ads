"""
Task 2: Reduce Lash Course campaign budget from $10/day to $5/day.
Campaign ID: 23696746455
"""
import json
from google.ads.googleads.client import GoogleAdsClient
from google.protobuf import field_mask_pb2

CUSTOMER_ID = "1682033495"
LOGIN_CUSTOMER_ID = "8081286543"
DEV_TOKEN = "XoDTB2_BCNajdX8kx2zlRg"
CREDENTIALS_PATH = "/Users/bobbybot/Projects/mcp-google-ads/credentials.json"
CAMPAIGN_ID = "23696746455"

def main():
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
    client = GoogleAdsClient.load_from_dict(config, version="v23")
    ga_service = client.get_service("GoogleAdsService")

    # First get the campaign's budget resource name
    query = f"""
        SELECT campaign.campaign_budget
        FROM campaign
        WHERE campaign.id = {CAMPAIGN_ID}
    """
    response = ga_service.search(customer_id=CUSTOMER_ID, query=query)
    budget_resource = None
    for row in response:
        budget_resource = row.campaign.campaign_budget
        print(f"Budget resource: {budget_resource}")
        break

    if not budget_resource:
        print("ERROR: Could not find campaign budget resource")
        return

    # Now update the budget to $5/day (5,000,000 micros)
    campaign_budget_service = client.get_service("CampaignBudgetService")
    operation = client.get_type("CampaignBudgetOperation")
    budget = operation.update
    budget.resource_name = budget_resource
    budget.amount_micros = 5_000_000  # $5.00

    operation.update_mask = field_mask_pb2.FieldMask(paths=["amount_micros"])

    print(f"\nUpdating budget to $5/day...")
    try:
        response = campaign_budget_service.mutate_campaign_budgets(
            customer_id=CUSTOMER_ID,
            operations=[operation],
        )
        for result in response.results:
            print(f"Updated: {result.resource_name}")
        print("SUCCESS: Lash Course campaign budget set to $5/day")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    main()
