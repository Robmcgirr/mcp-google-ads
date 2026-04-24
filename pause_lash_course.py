"""Pause the Lash Course campaign (23696746455)."""
import json
from google.ads.googleads.client import GoogleAdsClient
from google.protobuf import field_mask_pb2

CUSTOMER_ID = "1682033495"
LOGIN_CUSTOMER_ID = "8081286543"
DEV_TOKEN = "XoDTB2_BCNajdX8kx2zlRg"
CREDENTIALS_PATH = "/Users/jamesmcgirr/Projects/mcp-google-ads/credentials.json"
CAMPAIGN_ID = "23696746455"

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
    campaign_service = client.get_service("CampaignService")

    operation = client.get_type("CampaignOperation")
    campaign = operation.update
    campaign.resource_name = f"customers/{CUSTOMER_ID}/campaigns/{CAMPAIGN_ID}"
    campaign.status = client.enums.CampaignStatusEnum.PAUSED
    operation.update_mask = field_mask_pb2.FieldMask(paths=["status"])

    response = campaign_service.mutate_campaigns(
        customer_id=CUSTOMER_ID, operations=[operation]
    )
    for result in response.results:
        print(f"Paused: {result.resource_name}")
    print("SUCCESS: Lash Course campaign paused.")

if __name__ == "__main__":
    main()
