"""
Fix BOOK_APPOINTMENT~WEBSITE conversion goal to be biddable.
Uses CustomerConversionGoalService via google-ads v30 (API v23).
"""
import json
from google.ads.googleads.client import GoogleAdsClient
from google.protobuf import field_mask_pb2

CUSTOMER_ID = "1682033495"
LOGIN_CUSTOMER_ID = "8081286543"
DEV_TOKEN = "XoDTB2_BCNajdX8kx2zlRg"
CREDENTIALS_PATH = "/Users/bobbybot/Projects/mcp-google-ads/credentials.json"

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

    # First, query current state of conversion goals
    ga_service = client.get_service("GoogleAdsService")
    query = """
        SELECT
            customer_conversion_goal.category,
            customer_conversion_goal.origin,
            customer_conversion_goal.biddable
        FROM customer_conversion_goal
    """
    print("=== Current Conversion Goals ===")
    response = ga_service.search(customer_id=CUSTOMER_ID, query=query)
    for row in response:
        goal = row.customer_conversion_goal
        print(f"Category: {goal.category.name}, Origin: {goal.origin.name}, Biddable: {goal.biddable}")

    # Now update BOOK_APPOINTMENT~WEBSITE to biddable=true
    conv_goal_service = client.get_service("CustomerConversionGoalService")

    # Build the operation
    operation = client.get_type("CustomerConversionGoalOperation")
    goal = operation.update
    goal.resource_name = (
        f"customers/{CUSTOMER_ID}/customerConversionGoals/"
        "BOOK_APPOINTMENT~WEBSITE"
    )
    goal.biddable = True

    # Set field mask
    operation.update_mask = field_mask_pb2.FieldMask(paths=["biddable"])

    print("\n=== Updating BOOK_APPOINTMENT~WEBSITE to biddable=true ===")
    try:
        response = conv_goal_service.mutate_customer_conversion_goals(
            customer_id=CUSTOMER_ID,
            operations=[operation],
        )
        for result in response.results:
            print(f"Updated: {result.resource_name}")
        print("SUCCESS: BOOK_APPOINTMENT conversion goal is now biddable!")
    except Exception as e:
        print(f"ERROR: {e}")

    # Verify the change
    print("\n=== Verification ===")
    response = ga_service.search(customer_id=CUSTOMER_ID, query=query)
    for row in response:
        goal = row.customer_conversion_goal
        print(f"Category: {goal.category.name}, Origin: {goal.origin.name}, Biddable: {goal.biddable}")

if __name__ == "__main__":
    main()
