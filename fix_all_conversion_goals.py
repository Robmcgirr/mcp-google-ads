"""
Fix conversion goals for Lavilash Google Ads account.
Sets BOOK_APPOINTMENT~WEBSITE as the only biddable conversion goal.
"""
import json
from google.ads.googleads.client import GoogleAdsClient
from google.protobuf import field_mask_pb2

CUSTOMER_ID = "1682033495"
LOGIN_CUSTOMER_ID = "8081286543"
DEV_TOKEN = "XoDTB2_BCNajdX8kx2zlRg"
CREDENTIALS_PATH = "/Users/jamesmcgirr/Projects/mcp-google-ads/credentials.json"

# Goals to make biddable (these fire real conversions)
BIDDABLE_GOALS = [
    "BOOK_APPOINTMENT~WEBSITE",
]

def main() -> None:
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
    conv_goal_service = client.get_service("CustomerConversionGoalService")

    # Query current state
    query = """
        SELECT
            customer_conversion_goal.category,
            customer_conversion_goal.origin,
            customer_conversion_goal.biddable
        FROM customer_conversion_goal
    """
    print("=== Current Conversion Goals ===")
    response = ga_service.search(customer_id=CUSTOMER_ID, query=query)
    goals = []
    for row in response:
        goal = row.customer_conversion_goal
        key = f"{goal.category.name}~{goal.origin.name}"
        goals.append(key)
        print(f"  {key}: biddable={goal.biddable}")

    # Update goals
    operations = []
    for goal_key in goals:
        should_be_biddable = goal_key in BIDDABLE_GOALS
        operation = client.get_type("CustomerConversionGoalOperation")
        goal = operation.update
        goal.resource_name = (
            f"customers/{CUSTOMER_ID}/customerConversionGoals/{goal_key}"
        )
        goal.biddable = should_be_biddable
        operation.update_mask = field_mask_pb2.FieldMask(paths=["biddable"])
        operations.append(operation)
        print(f"\n  Setting {goal_key} → biddable={should_be_biddable}")

    print("\n=== Applying Changes ===")
    try:
        response = conv_goal_service.mutate_customer_conversion_goals(
            customer_id=CUSTOMER_ID,
            operations=operations,
        )
        for result in response.results:
            print(f"  Updated: {result.resource_name}")
        print("\nSUCCESS: Conversion goals updated!")
    except Exception as e:
        print(f"\nERROR: {e}")

    # Verify
    print("\n=== Verification ===")
    response = ga_service.search(customer_id=CUSTOMER_ID, query=query)
    for row in response:
        goal = row.customer_conversion_goal
        key = f"{goal.category.name}~{goal.origin.name}"
        marker = "✓ PRIMARY" if goal.biddable else "  secondary"
        print(f"  {marker}  {key}")


if __name__ == "__main__":
    main()
