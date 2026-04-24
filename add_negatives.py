"""Add missing negative keywords to Leads-Search-1."""
import json
from google.ads.googleads.client import GoogleAdsClient
from google.protobuf import field_mask_pb2

CUSTOMER_ID = "1682033495"
LOGIN_CUSTOMER_ID = "8081286543"
DEV_TOKEN = "XoDTB2_BCNajdX8kx2zlRg"
CREDENTIALS_PATH = "/Users/jamesmcgirr/Projects/mcp-google-ads/credentials.json"
CAMPAIGN_ID = "20941360234"

PHRASE_NEGATIVES = [
    "eyebrow lamination", "eyebrow tint", "eyebrow waxing",
    "lavish nails", "russian manicure", "women salon",
    "aesthetics", "salon near me", "beauty parlor", "lash lift",
    "eyelash tint", "brow tint", "lash perm",
    "course", "training", "certification", "school", "class",
    "learn", "become a", "license", "academy",
    "kit", "bulk", "amazon", "walmart", "at home",
    "glue", "remover", "mascara", "adhesive", "fake lashes",
    "salary", "groupon", "coupon",
]

EXACT_NEGATIVES = [
    "lavish nails winnipeg", "korean lash lift winnipeg",
    "lash love", "lee lashes", "wimper lashes",
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
    campaign_criterion_service = client.get_service("CampaignCriterionService")

    operations = []

    for kw in PHRASE_NEGATIVES:
        op = client.get_type("CampaignCriterionOperation")
        criterion = op.create
        criterion.campaign = f"customers/{CUSTOMER_ID}/campaigns/{CAMPAIGN_ID}"
        criterion.negative = True
        criterion.keyword.text = kw
        criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum.PHRASE
        operations.append(op)

    for kw in EXACT_NEGATIVES:
        op = client.get_type("CampaignCriterionOperation")
        criterion = op.create
        criterion.campaign = f"customers/{CUSTOMER_ID}/campaigns/{CAMPAIGN_ID}"
        criterion.negative = True
        criterion.keyword.text = kw
        criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum.EXACT
        operations.append(op)

    print(f"Adding {len(operations)} negative keywords...")
    try:
        response = campaign_criterion_service.mutate_campaign_criteria(
            customer_id=CUSTOMER_ID,
            operations=operations,
        )
        added = 0
        for result in response.results:
            added += 1
        print(f"SUCCESS: {added} negative keywords added.")
    except Exception as e:
        error_str = str(e)
        if "DUPLICATE" in error_str.upper():
            print(f"Some duplicates detected (already exist). Non-duplicates were added.")
        else:
            print(f"ERROR: {e}")

if __name__ == "__main__":
    main()
