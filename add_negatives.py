"""
Tasks 3 & 4: Add negative keywords to campaigns.

Task 3: Add 16 negatives to Leads-Search-1 (20941360234)
Task 4: Add negatives to Brand (23701551017) and Course (23696746455)
"""
import json
from google.ads.googleads.client import GoogleAdsClient

CUSTOMER_ID = "1682033495"
LOGIN_CUSTOMER_ID = "8081286543"
DEV_TOKEN = "XoDTB2_BCNajdX8kx2zlRg"
CREDENTIALS_PATH = "/Users/bobbybot/Projects/mcp-google-ads/credentials.json"

# Campaign IDs
LEADS_SEARCH_1 = "20941360234"
BRAND_CAMPAIGN = "23701551017"
COURSE_CAMPAIGN = "23696746455"


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


def add_campaign_negatives(client, customer_id, campaign_id, keywords_with_match):
    """Add negative keywords to a campaign using CampaignCriterionService."""
    campaign_criterion_service = client.get_service("CampaignCriterionService")
    operations = []

    for keyword_text, match_type in keywords_with_match:
        operation = client.get_type("CampaignCriterionOperation")
        criterion = operation.create
        criterion.campaign = f"customers/{customer_id}/campaigns/{campaign_id}"
        criterion.negative = True
        criterion.keyword.text = keyword_text
        # match_type: EXACT=2, PHRASE=3, BROAD=4
        criterion.keyword.match_type = match_type
        operations.append(operation)

    try:
        response = campaign_criterion_service.mutate_campaign_criteria(
            customer_id=customer_id,
            operations=operations,
        )
        print(f"  Added {len(response.results)} negative keywords")
        for result in response.results:
            print(f"    -> {result.resource_name}")
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def main():
    client = get_client()

    # Match type enums
    from google.ads.googleads.v23.enums.types.keyword_match_type import (
        KeywordMatchTypeEnum,
    )
    EXACT = KeywordMatchTypeEnum.KeywordMatchType.EXACT
    PHRASE = KeywordMatchTypeEnum.KeywordMatchType.PHRASE

    # Task 3: Leads-Search-1 negatives
    print(f"=== TASK 3: Adding negatives to Leads-Search-1 ({LEADS_SEARCH_1}) ===")
    leads_negatives = [
        # Phrase match
        ("brow lamination", PHRASE),
        ("nano brows", PHRASE),
        ("lash tinting only", PHRASE),
        ("semi permanent eyeliner", PHRASE),
        ("fibroblast", PHRASE),
        ("plasma pen", PHRASE),
        ("dermaplaning", PHRASE),
        ("chemical peel", PHRASE),
        ("microneedling", PHRASE),
        ("facials near me", PHRASE),
        ("beauty school", PHRASE),
        ("esthetician school", PHRASE),
        # Exact match
        ("fabutan", EXACT),
        ("eye candy", EXACT),
        ("beauty boutique winnipeg", EXACT),
        ("glamour secrets", EXACT),
    ]
    add_campaign_negatives(client, CUSTOMER_ID, LEADS_SEARCH_1, leads_negatives)

    # Task 4a: Brand campaign negatives
    print(f"\n=== TASK 4a: Adding negatives to Brand ({BRAND_CAMPAIGN}) ===")
    brand_negatives = [
        ("jobs", PHRASE),
        ("hiring", PHRASE),
        ("careers", PHRASE),
        ("complaints", PHRASE),
        ("reviews", PHRASE),
        ("coupon", PHRASE),
        ("groupon", PHRASE),
    ]
    add_campaign_negatives(client, CUSTOMER_ID, BRAND_CAMPAIGN, brand_negatives)

    # Task 4b: Course campaign negatives
    print(f"\n=== TASK 4b: Adding negatives to Course ({COURSE_CAMPAIGN}) ===")
    course_negatives = [
        ("free course", PHRASE),
        ("online course", PHRASE),
        ("youtube tutorial", PHRASE),
        ("diy lashes", PHRASE),
        ("how to", PHRASE),
    ]
    add_campaign_negatives(client, CUSTOMER_ID, COURSE_CAMPAIGN, course_negatives)

    print("\n=== ALL NEGATIVE KEYWORDS COMPLETE ===")


if __name__ == "__main__":
    main()
