"""
Task 5: Create call asset (extension) with phone (204) 505-5274
and link it to all enabled campaigns.
"""
import json
from google.ads.googleads.client import GoogleAdsClient

CUSTOMER_ID = "1682033495"
LOGIN_CUSTOMER_ID = "8081286543"
DEV_TOKEN = "XoDTB2_BCNajdX8kx2zlRg"
CREDENTIALS_PATH = "/Users/bobbybot/Projects/mcp-google-ads/credentials.json"

CAMPAIGNS = ["20941360234", "23696746455", "23701551017"]

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

    # Step 1: Create the call asset
    asset_service = client.get_service("AssetService")
    operation = client.get_type("AssetOperation")
    call_asset = operation.create
    call_asset.name = "LaviLash Phone"
    call_asset.type_ = client.enums.AssetTypeEnum.CALL
    call_asset.call_asset.country_code = "CA"
    call_asset.call_asset.phone_number = "2045055274"
    call_asset.call_asset.call_conversion_reporting_state = (
        client.enums.CallConversionReportingStateEnum.USE_RESOURCE_LEVEL_CALL_CONVERSION_ACTION
    )

    print("Creating call asset...")
    try:
        response = asset_service.mutate_assets(
            customer_id=CUSTOMER_ID,
            operations=[operation],
        )
        asset_resource = response.results[0].resource_name
        print(f"Created: {asset_resource}")
    except Exception as e:
        print(f"ERROR creating asset: {e}")
        # Try to find existing call asset
        ga_service = client.get_service("GoogleAdsService")
        query = """
            SELECT asset.resource_name, asset.call_asset.phone_number
            FROM asset
            WHERE asset.type = 'CALL'
        """
        resp = ga_service.search(customer_id=CUSTOMER_ID, query=query)
        for row in resp:
            print(f"Existing call asset: {row.asset.resource_name} - {row.asset.call_asset.phone_number}")
            asset_resource = row.asset.resource_name
        if 'asset_resource' not in dir():
            print("No existing call asset found. Cannot proceed.")
            return

    # Step 2: Link the call asset to each campaign
    campaign_asset_service = client.get_service("CampaignAssetService")
    operations = []
    for campaign_id in CAMPAIGNS:
        op = client.get_type("CampaignAssetOperation")
        campaign_asset = op.create
        campaign_asset.campaign = f"customers/{CUSTOMER_ID}/campaigns/{campaign_id}"
        campaign_asset.asset = asset_resource
        campaign_asset.field_type = client.enums.AssetFieldTypeEnum.CALL
        operations.append(op)

    print(f"\nLinking call asset to {len(CAMPAIGNS)} campaigns...")
    try:
        response = campaign_asset_service.mutate_campaign_assets(
            customer_id=CUSTOMER_ID,
            operations=operations,
        )
        for result in response.results:
            print(f"  Linked: {result.resource_name}")
        print("SUCCESS: Call extension added to all campaigns!")
    except Exception as e:
        print(f"ERROR linking to campaigns: {e}")


if __name__ == "__main__":
    main()
