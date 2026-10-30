import requests
import pandas as pd
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GRAPHQL_URL = "https://mmiconnect.in/graphql"
GROUP = "ep-blr-2026"
SHOW_ID = 122

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://mmiconnect.in",
    "Referer": "https://mmiconnect.in/app/catalogue/exhibitors/ep-blr-2026?first=814",
    "User-Agent": "Mozilla/5.0"
}

LIST_QUERY = """
query getExhibitorListForGroup(
  $where: [WhereExpression!]
  $first: Int
  $after: Int
  $categoryIds: [Int]
  $keyword: String
  $group: String
) {
  catalogueQueries {
    exhibitorsWithWishListGroup(
      first: $first
      where: $where
      after: $after
      categoryIds: $categoryIds
      keyword: $keyword
      group: $group
    ) {
      totalCount
      exhibitors {
        customer {
          id
          userId
          companyName
        }
      }
    }
  }
}
"""

DETAIL_QUERY = """
query getExibitorDetailsForGroup(
  $userId: String
  $showId: Int
) {
  globalAnonymousQueries {
    customers(userId: $userId, showId: $showId) {
      companyName
      website
      address1
      address2
      city
      state
      postalCode
      country
      exhibitorDetail {
        exhibitorType
      }
      customerCategories {
        category {
          mainCategory
          subCategory
          categoryName
        }
      }
    }
  }
}
"""

def graphql(query, variables, referer=None):
    headers = HEADERS.copy()
    if referer:
        headers["Referer"] = referer

    response = requests.post(
        GRAPHQL_URL,
        json={
            "operationName": (
                "getExhibitorListForGroup"
                if "getExhibitorListForGroup" in query
                else "getExibitorDetailsForGroup"
            ),
            "variables": variables,
            "query": query
        },
        headers=headers,
        timeout=60
    )
    response.raise_for_status()

    data = response.json()

    if data.get("errors"):
        raise RuntimeError(data["errors"])

    return data["data"]


print("Getting exhibitor list...")

list_variables = {
    "where": [],
    "group": GROUP,
    "first": 814,
    "after": -1
}

data = graphql(LIST_QUERY, list_variables)

result = data["catalogueQueries"]["exhibitorsWithWishListGroup"]
total = result["totalCount"]
exhibitors = result["exhibitors"]

print(f"Total exhibitors reported by website: {total}")
print(f"Exhibitor records received: {len(exhibitors)}")

rows = []

for index, item in enumerate(exhibitors, start=1):
    customer = item.get("customer") or {}
    user_id = customer.get("userId")

    if not user_id:
        print(f"[{index}/{len(exhibitors)}] Skipping record without userId")
        continue

    try:
        detail_variables = {
            "userId": user_id,
            "showId": SHOW_ID
        }

        detail_data = graphql(
            DETAIL_QUERY,
            detail_variables,
            referer=(
                f"https://mmiconnect.in/app/catalogue/exhibitor-detail/"
                f"{GROUP}/{SHOW_ID}/{user_id}"
            )
        )

        customers = detail_data["globalAnonymousQueries"]["customers"]
        if isinstance(customers, list):
            detail = customers[0] if customers else {}
        elif isinstance(customers, dict):
            detail = customers
        else:
            detail = {}

        exhibitor_detail = detail.get("exhibitorDetail") or {}
        categories = detail.get("customerCategories") or []

        category_names = []
        main_categories = []
        sub_categories = []

        for cat_item in categories:
            category = cat_item.get("category") or {}

            for value, target in [
                (category.get("categoryName"), category_names),
                (category.get("mainCategory"), main_categories),
                (category.get("subCategory"), sub_categories),
            ]:
                if value and str(value).strip() and str(value).strip() not in target:
                    target.append(str(value).strip())

        rows.append({
            "Company Name": detail.get("companyName") or customer.get("companyName"),
            "Company Type": exhibitor_detail.get("exhibitorType"),
            "Industry / Category": ", ".join(category_names),
            "Main Category": ", ".join(main_categories),
            "Sub Category": ", ".join(sub_categories),
            "Website": detail.get("website"),
            "Address": " ".join(
                str(x).strip()
                for x in [
                    detail.get("address1"),
                    detail.get("address2"),
                    detail.get("city"),
                    detail.get("state"),
                    detail.get("postalCode"),
                    detail.get("country")
                ]
                if x and str(x).strip()
            )
        })

        print(f"[{index}/{len(exhibitors)}] {rows[-1]['Company Name']}")

    except Exception as e:
        print(f"[{index}/{len(exhibitors)}] Error for {customer.get('companyName')}: {e}")
        rows.append({
            "Company Name": customer.get("companyName"),
            "Company Type": "",
            "Industry / Category": "",
            "Main Category": "",
            "Sub Category": "",
            "Website": "",
            "Address": ""
        })

    # Small delay so we don't hammer the public endpoint.
    time.sleep(0.15)

df = pd.DataFrame(rows)

# Remove exact duplicate companies while preserving the first occurrence.
df = df.drop_duplicates(subset=["Company Name"], keep="first")

output = "EP_BLR_2026_Company_Careers_Database.xlsx"
df.to_excel(output, index=False)

print("\nFinished!")
print(f"Companies saved: {len(df)}")
print(f"Excel file: {output}")
