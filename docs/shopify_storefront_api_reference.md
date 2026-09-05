# Shopify Storefront API Reference (2024-04)

[![API Version: 2024-04](https://img.shields.io/badge/API_Version-2024--04-blue.svg)](https://shopify.dev/docs/api/storefront/2024-04)
[![Protocol: GraphQL](https://img.shields.io/badge/Protocol-GraphQL_POST-008060.svg)](https://shopify.dev/docs/api/storefront)
[![Status: Production Verified](https://img.shields.io/badge/Status-Verified_Live-success.svg)](https://rasor-test-store-1.myshopify.com)
[![Gateway REST Specification](https://img.shields.io/badge/Gateway_REST-API_Specification-009688.svg)](API_SPECIFICATION.md)
[![Headless Architecture](https://img.shields.io/badge/Shopify-Headless_Architecture-orange.svg)](shopify_investigation.md)
[![Interactive OpenAPI Explorer](https://img.shields.io/badge/OpenAPI_UI-http%3A%2F%2Flocalhost%3A8000%2Fdocs-blue.svg)](http://localhost:8000/docs)

A comprehensive, production-validated technical reference for the Shopify Storefront GraphQL API (**2024-04**), specifically curated and verified for the **Rasor Autonomous Agentic Commerce Engine**. This specification details headless catalog discovery, progressive search fallback queries, headless cart mutations, buyer identity binding, and checkout URL generation.

> [!TIP]
> **Unified Architecture & Live Interactive Testing:**
> * For the orchestrating FastAPI Gateway REST routes, ACP-2026.1 discovery feed, and AP2 spending mandates, see [**API_SPECIFICATION.md**](API_SPECIFICATION.md).
> * For the architectural journey from upstream scraping to headless settlement, see [**shopify_investigation.md**](shopify_investigation.md).
> * Launch the application gateway with `./start.sh` and explore all 43 live REST endpoints interactively via Swagger UI at [`http://localhost:8000/docs`](http://localhost:8000/docs).
> * For the Shopify Storefront GraphQL playground (direct query execution), see the embedded **[GraphQL Console at `http://localhost:8000/shopify-console`](http://localhost:8000/shopify-console)**.



---

## Table of Contents
1. [Overview & Authentication](#1-overview--authentication)
   - [Endpoint & Headers](#11-endpoint--headers)
   - [Storefront Access Scopes](#12-storefront-access-scopes)
   - [Storefront API vs. Admin API Constraints](#13-storefront-api-vs-admin-api-constraints)
2. [Queries (Read Operations)](#2-queries-read-operations)
   - [2.1 products — Catalog Browsing & Filtered Listings](#21-products--catalog-browsing--filtered-listings)
   - [2.2 product — Single Product Inspection by ID or Handle](#22-product--single-product-inspection-by-id-or-handle)
   - [2.3 search — Full-Text Relevance Search](#23-search--full-text-relevance-search)
   - [2.4 predictiveSearch — Typeahead Autocomplete](#24-predictivesearch--typeahead-autocomplete)
   - [2.5 collections — Collection Catalog List](#25-collections--collection-catalog-list)
   - [2.6 collection — Products by Collection Handle](#26-collection--products-by-collection-handle)
   - [2.7 cart — Cart State & Checkout URL Inspection](#27-cart--cart-state--checkout-url-inspection)
   - [2.8 customer — Authenticated Customer Profile & Orders](#28-customer--authenticated-customer-profile--orders)
   - [2.9 shop — Store Metadata & Policies](#29-shop--store-metadata--policies)
   - [2.10 localization — Country, Currency & Language Context](#210-localization--country-currency--language-context)
   - [2.11 metaobject & metaobjects — Custom CMS Metadata](#211-metaobject--metaobjects--custom-cms-metadata)
   - [2.12 productRecommendations — Algorithmic Suggestions](#212-productrecommendations--algorithmic-suggestions)
   - [2.13 node & nodes — Generic GID Lookup](#213-node--nodes--generic-gid-lookup)
   - [2.14 articles & blogs — Editorial Content](#214-articles--blogs--editorial-content)
   - [2.15 pages — Static Store Pages](#215-pages--static-store-pages)
   - [2.16 sellingPlanGroups — Subscription Plans](#216-sellingplangroups--subscription-plans)
   - [2.17 urlRedirects — URL Routing Mappings](#217-urlredirects--url-routing-mappings)
3. [Mutations (Write Operations)](#3-mutations-write-operations)
   - [3.1 Cart Mutations](#31-cart-mutations)
     - [3.1.1 cartCreate — Initialize Shopping Cart](#311-cartcreate--initialize-shopping-cart)
     - [3.1.2 cartLinesAdd — Append Garments to Cart](#312-cartlinesadd--append-garments-to-cart)
     - [3.1.3 cartLinesRemove — Evict Line Items](#313-cartlinesremove--evict-line-items)
     - [3.1.4 cartLinesUpdate — Modify Variant Quantities](#314-cartlinesupdate--modify-variant-quantities)
     - [3.1.5 cartNoteUpdate — Attach Autonomous Agent Notes](#315-cartnoteupdate--attach-autonomous-agent-notes)
     - [3.1.6 cartDiscountCodesUpdate — Apply Promotional Vouchers](#316-cartdiscountcodesupdate--apply-promotional-vouchers)
     - [3.1.7 cartBuyerIdentityUpdate — Attach Shopper & Shipping Address](#317-cartbuyeridentityupdate--attach-shopper--shipping-address)
     - [3.1.8 cartAttributesUpdate — Attach Session Metadata](#318-cartattributesupdate--attach-session-metadata)
     - [3.1.9 cartGiftCardCodesUpdate — Apply Stored Value Codes](#319-cartgiftcardcodesupdate--apply-stored-value-codes)
   - [3.2 Customer Authentication Mutations](#32-customer-authentication-mutations)
     - [3.2.1 customerCreate — Account Registration](#321-customercreate--account-registration)
     - [3.2.2 customerAccessTokenCreate — Customer Login](#322-customeraccesstokencreate--customer-login)
     - [3.2.3 customerAccessTokenDelete — Customer Logout](#323-customeraccesstokendelete--customer-logout)
     - [3.2.4 customerAccessTokenRenew — Session Renewal](#324-customeraccesstokenrenew--session-renewal)
     - [3.2.5 customerUpdate — Profile Update](#325-customerupdate--profile-update)
     - [3.2.6 customerRecover & customerReset — Password Recovery](#326-customerrecover--customerreset--password-recovery)
     - [3.2.7 Customer Address Mutations](#327-customer-address-mutations)
   - [3.3 Deprecated Mutations](#33-deprecated-mutations)
4. [Directives & Advanced Storefront Patterns](#4-directives--advanced-storefront-patterns)
   - [4.1 @inContext Directive — Localization & Presentment Currencies](#41-incontext-directive--localization--presentment-currencies)
   - [4.2 Cursor-Based Pagination Standard](#42-cursor-based-pagination-standard)
   - [4.3 Storefront-Accessible Metafields](#43-storefront-accessible-metafields)
   - [4.4 Asynchronous Bulk Operations](#44-asynchronous-bulk-operations)
5. [Rasor Implementation Architecture](#5-rasor-implementation-architecture)
   - [5.1 5-Tier Progressive Retrieval Strategy](#51-5-tier-progressive-retrieval-strategy)
   - [5.2 Headless Cart & AP2 Mandate Pipeline](#52-headless-cart--ap2-mandate-pipeline)
   - [5.3 Production Credentials & Environment Setup](#53-production-credentials--environment-setup)
6. [API Quick Reference Cheat Sheet](#6-api-quick-reference-cheat-sheet)
   - [Queries Matrix (18 Operations)](#queries-matrix-18-operations)
   - [Mutations Matrix (20 Operations)](#mutations-matrix-20-operations)

---

## 1. Overview & Authentication

### 1.1 Endpoint & Headers
All Storefront API operations can be executed either directly against Shopify or through the Rasor Gateway GraphQL proxy:

#### Direct Shopify Storefront Endpoint:
```http
POST https://rasor-test-store-1.myshopify.com/api/2024-04/graphql.json
Content-Type: application/json
X-Shopify-Storefront-Access-Token: {SHOPIFY_STOREFRONT_TOKEN}
```

#### Rasor Gateway Proxy Endpoint (Zero-CORS, Managed Auth):
```http
POST http://localhost:8000/api/shopify/graphql
Content-Type: application/json

{
  "query": "query { shop { name currencyCode } }"
}
```

#### Interactive Developer GraphQL Console:
* Web Playground: **[`http://localhost:8000/shopify-console`](http://localhost:8000/shopify-console)** (pre-configured with 8 curated queries/mutations and live schema introspection).

> [!IMPORTANT]
> **Token Obligation & Distinction:**
> * **Storefront Access Token (`SHOPIFY_STOREFRONT_TOKEN` / `SHOPIFY_STOREFRONT_ACCESS_TOKEN`):** Public 32-character hexadecimal key (`6a1c1b2f3f1fafd8afc7040ed4e19307`). Passed via `X-Shopify-Storefront-Access-Token` for headless queries and cart operations.
> * **Admin API Token (`SHOPIFY_ADMIN_TOKEN`):** Secret token beginning with `shpat_...`. Passed via `X-Shopify-Access-Token` exclusively for `/admin/api/2024-04/` order creation and settlement. Passing a `shpat_...` token to the Storefront API will result in `UNAUTHORIZED`.

### 1.2 Storefront Access Scopes
The following access scopes are enabled and verified for `rasor-test-store-1`:

| Access Scope | Operational Capability |
| :--- | :--- |
| `unauthenticated_read_product_listings` | Query public product catalog, variants, pricing, and images |
| `unauthenticated_read_product_inventory` | Query `availableForSale` inventory flags across variants |
| `unauthenticated_read_product_tags` | Filter catalog by gender, franchise, and merchandising tags |
| `unauthenticated_read_content` | Fetch store static pages, blog articles, and policy content |
| `unauthenticated_write_checkouts` | Initialize and manipulate headless carts via Storefront GraphQL |
| `unauthenticated_read_checkouts` | Inspect cart line items, pricing breakdowns, and checkout URLs |
| `unauthenticated_write_customers` | Register customer accounts and update delivery addresses |
| `unauthenticated_read_customers` | Retrieve profile metadata, saved addresses, and past order history |
| `unauthenticated_read_customer_tags` | Inspect customer tier tags for personalized pricing rules |
| `unauthenticated_read_metaobjects` | Query custom CMS entities and dynamic taxonomy tables |
| `unauthenticated_read_product_pickup_locations` | Query local store fulfillment hubs for physical pickup |
| `unauthenticated_read_selling_plans` | Retrieve recurring subscription plans and bulk discounts |
| `unauthenticated_write_bulk_operations` | Submit large-scale asynchronous catalog query operations |
| `unauthenticated_read_bulk_operations` | Poll status and fetch JSONL results of bulk jobs |
| `unauthenticated_read_bundles` | Inspect multi-piece bundle configurations and variant linkages |
| `unauthenticated_read_shop_pay_installments_pricing` | Fetch installments pricing schedules |

### 1.3 Storefront API vs. Admin API Constraints

> [!WARNING]
> **Storefront Query Pitfalls:** The Storefront API enforces strict predicate limitations compared to the Admin API. Using Admin-only filters on the Storefront API will not error—they will **silently fail** and return 0 results.

| Predicate / Field | Storefront API Support | Admin API Support | Resolution Strategy in Rasor |
| :--- | :---: | :---: | :--- |
| `variants.price:<=N` | ❌ Silently Fails | ✅ Supported | **Client-Side Filtering:** Retrieve candidates matching taxonomy/tags and filter price bounds in Python (`shopify_api.py`). |
| `inventory_quantity:>N` | ❌ Unsupported | ✅ Supported | **Binary Availability:** Use `available_for_sale:true`. Precise quantity is verified at checkout settlement. |
| `metafield by owner` | ❌ Unsupported | ✅ Supported | **Namespace Lookup:** Use `metafields(identifiers: [{namespace: "custom", key: "..."}])` marked storefront-accessible. |
| `product_type:TYPE` | ✅ Valid | ✅ Supported | Primary predicate for Tier 1 and Tier 4 category retrieval. |
| `tag:TAG` | ✅ Valid | ✅ Supported | Used for gender filtering (`tag:Men`, `tag:Women`) and character tags (`tag:batman`). |
| `title:TERM` | ✅ Valid | ✅ Supported | Exact and prefix title matching. |
| `available_for_sale:true` | ✅ Valid | ✅ Supported | Filters out out-of-stock items before candidate scoring. |

---

## 2. Queries (Read Operations)

### 2.1 products — Catalog Browsing & Filtered Listings
* **Purpose:** Primary catalog exploration with cursor pagination and server-side boolean search predicates.
* **Rasor Use Case:** Tier 1 and Tier 4 discovery retrieval in `ShopifyCatalogProvider`.
* **Verified Status:** ✅ Active on `rasor-test-store-1`.

```graphql
query GetFilteredProducts {
  products(
    first: 20
    query: "product_type:T-Shirt AND tag:Men AND available_for_sale:true"
    sortKey: RELEVANCE
  ) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        id
        handle
        title
        description
        productType
        vendor
        tags
        availableForSale
        variants(first: 30) {
          edges {
            node {
              id
              title
              price {
                amount
                currencyCode
              }
              compareAtPrice {
                amount
              }
              availableForSale
            }
          }
        }
        images(first: 5) {
          edges {
            node {
              url
              altText
            }
          }
        }
      }
    }
  }
}
```

* **Sort Keys:** `TITLE`, `PRODUCT_TYPE`, `VENDOR`, `UPDATED_AT`, `CREATED_AT`, `PRICE`, `BEST_SELLING`, `RELEVANCE`, `ID`.
* **Pagination:** Pass `after: "CURSOR"` with the `endCursor` string for subsequent pages.

---

### 2.2 product — Single Product Inspection by ID or Handle
* **Purpose:** Retrieve complete PDP metadata for a single product.
* **Rasor Use Case:** Deep verification in Tier 2 before multimodal VQA and color analysis.
* **Verified Status:** ✅ Active on `rasor-test-store-1`.

#### By Handle:
```graphql
query GetProductByHandle {
  product(handle: "mens-black-batman-t-shirt") {
    id
    handle
    title
    description
    productType
    vendor
    tags
    availableForSale
    variants(first: 50) {
      edges {
        node {
          id
          title
          price {
            amount
            currencyCode
          }
          compareAtPrice {
            amount
          }
          availableForSale
          selectedOptions {
            name
            value
          }
          image {
            url
            altText
          }
        }
      }
    }
    images(first: 10) {
      edges {
        node {
          url
          altText
        }
      }
    }
    metafields(identifiers: [{ namespace: "custom", key: "fabric" }]) {
      key
      value
    }
  }
}
```

#### By Global ID (GID):
```graphql
query GetProductByGID {
  product(id: "gid://shopify/Product/123456789") {
    id
    title
    availableForSale
  }
}
```

---

### 2.3 search — Full-Text Relevance Search
* **Purpose:** Search & Discovery engine supporting typo tolerance, boosts, and prefix matching.
* **Rasor Use Case:** Tier 2 progressive fallback for conversational keywords.
* **Verified Status:** ✅ Active on `rasor-test-store-1`.

```graphql
query FullTextSearch {
  search(
    query: "batman t-shirt"
    types: [PRODUCT]
    first: 20
    prefix: LAST
  ) {
    totalCount
    edges {
      node {
        ... on Product {
          id
          handle
          title
          variants(first: 5) {
            edges {
              node {
                price {
                  amount
                }
              }
            }
          }
          images(first: 1) {
            edges {
              node {
                url
              }
            }
          }
        }
      }
    }
    productFilters {
      id
      label
      type
      values {
        count
        label
        input
      }
    }
  }
}
```

* **Prefix Enum:** `LAST` (enables partial-word matching on final token) or `NONE` (exact word match only).
* **Search Types:** `PRODUCT`, `PAGE`, `ARTICLE`.

---

### 2.4 predictiveSearch — Typeahead Autocomplete
* **Purpose:** Real-time search-as-you-type suggestions with minimal payload.
* **Rasor Use Case:** Natural language UI search box autocomplete.
* **Verified Status:** ✅ Active on `rasor-test-store-1`.

```graphql
query PredictiveSearchAutocomplete {
  predictiveSearch(query: "bat", types: [PRODUCT]) {
    products {
      id
      handle
      title
      variants(first: 1) {
        edges {
          node {
            price {
              amount
            }
          }
        }
      }
      images(first: 1) {
        edges {
          node {
            url
          }
        }
      }
    }
    collections {
      id
      handle
      title
    }
    pages {
      id
      handle
      title
    }
  }
}
```

---

### 2.5 collections — Collection Catalog List
* **Purpose:** Browse all store collections for navigational structuring.
* **Verified Status:** ✅ Active on `rasor-test-store-1`.

```graphql
query ListCollections {
  collections(first: 50, sortKey: UPDATED_AT) {
    edges {
      node {
        id
        handle
        title
        description
        image {
          url
          altText
        }
        products(first: 5) {
          edges {
            node {
              id
              title
            }
          }
        }
      }
    }
  }
}
```

---

### 2.6 collection — Products by Collection Handle
* **Purpose:** Query products categorized within a specific collection handle.
* **Verified Status:** ✅ Active on `rasor-test-store-1`.

```graphql
query GetProductsInCollection {
  collection(handle: "t-shirts") {
    id
    title
    description
    products(first: 50, sortKey: BEST_SELLING) {
      pageInfo {
        hasNextPage
        endCursor
      }
      edges {
        node {
          id
          handle
          title
          variants(first: 10) {
            edges {
              node {
                price {
                  amount
                }
                availableForSale
              }
            }
          }
        }
      }
    }
  }
}
```

---

### 2.7 cart — Cart State & Checkout URL Inspection
* **Purpose:** Retrieve live cart contents, itemized costs, tax estimates, applied discount codes, and hosted checkout URL.
* **Rasor Use Case:** Validating cart payload before signing AP2 Mandate SHA-256 hash.
* **Verified Status:** ✅ Active on `rasor-test-store-1`.

```graphql
query GetCartDetails {
  cart(id: "gid://shopify/Cart/abc123456789") {
    id
    checkoutUrl
    createdAt
    updatedAt
    totalQuantity
    cost {
      totalAmount {
        amount
        currencyCode
      }
      subtotalAmount {
        amount
        currencyCode
      }
      totalTaxAmount {
        amount
        currencyCode
      }
    }
    discountCodes {
      code
      applicable
    }
    lines(first: 50) {
      edges {
        node {
          id
          quantity
          merchandise {
            ... on ProductVariant {
              id
              title
              price {
                amount
                currencyCode
              }
              product {
                handle
                title
              }
            }
          }
          cost {
            totalAmount {
              amount
              currencyCode
            }
            amountPerQuantity {
              amount
              currencyCode
            }
          }
        }
      }
    }
  }
}
```

---

### 2.8 customer — Authenticated Customer Profile & Orders
* **Purpose:** Retrieve shopper profile details, default shipping address, and order history.
* **Prerequisite:** Requires a valid `customerAccessToken` from `customerAccessTokenCreate`.
* **Verified Status:** ✅ Active on `rasor-test-store-1`.

```graphql
query GetCustomerProfile {
  customer(customerAccessToken: "USER_SESSION_ACCESS_TOKEN") {
    id
    email
    firstName
    lastName
    phone
    defaultAddress {
      firstName
      lastName
      address1
      city
      province
      country
      zip
    }
    orders(first: 10) {
      edges {
        node {
          id
          orderNumber
          processedAt
          totalPriceV2 {
            amount
            currencyCode
          }
          lineItems(first: 20) {
            edges {
              node {
                title
                quantity
              }
            }
          }
        }
      }
    }
  }
}
```

---

### 2.9 shop — Store Metadata & Policies
* **Purpose:** Retrieve global store settings, operational currencies, shipping countries, and legal policies.
* **Verified Status:** ✅ Active on `rasor-test-store-1`.

```graphql
query GetShopPoliciesAndCurrencies {
  shop {
    name
    description
    primaryDomain {
      url
    }
    currencyCode
    shipsToCountries
    paymentSettings {
      acceptedCardBrands
      enabledPresentmentCurrencies
    }
    privacyPolicy {
      title
      body
    }
    termsOfService {
      title
      body
    }
    refundPolicy {
      title
      body
    }
  }
}
```

---

### 2.10 localization — Country, Currency & Language Context
* **Purpose:** Discover supported countries, ISO currency symbols, and languages for dynamic localization.
* **Verified Status:** ✅ Active on `rasor-test-store-1`.

```graphql
query GetLocalizationSettings {
  localization {
    availableCountries {
      isoCode
      name
      currency {
        isoCode
        name
        symbol
      }
    }
    availableLanguages {
      isoCode
      name
      endonymName
    }
    country {
      isoCode
      name
    }
    language {
      isoCode
      name
    }
  }
}
```

---

### 2.11 metaobject & metaobjects — Custom CMS Metadata
* **Purpose:** Query structured custom entities (e.g. style guides, size charts, FAQ items).
* **Verified Status:** ✅ Active on `rasor-test-store-1`.

#### By GID:
```graphql
query GetMetaobjectByGID {
  metaobject(id: "gid://shopify/Metaobject/123") {
    id
    handle
    type
    fields {
      key
      value
    }
  }
}
```

#### By Type:
```graphql
query ListMetaobjectsByType {
  metaobjects(type: "faq_item", first: 10) {
    edges {
      node {
        handle
        fields {
          key
          value
        }
      }
    }
  }
}
```

---

### 2.12 productRecommendations — Algorithmic Suggestions
* **Purpose:** Fetch Shopify's recommendation engine output for complementary or alternative items.
* **Verified Status:** ✅ Active on `rasor-test-store-1`.

```graphql
query GetRecommendations {
  productRecommendations(productId: "gid://shopify/Product/12345") {
    id
    handle
    title
    variants(first: 1) {
      edges {
        node {
          price {
            amount
          }
        }
      }
    }
    images(first: 1) {
      edges {
        node {
          url
        }
      }
    }
  }
}
```

---

### 2.13 node & nodes — Generic GID Lookup
* **Purpose:** Direct polymorphic retrieval of any entity by its Global Identifier.
* **Verified Status:** ✅ Active on `rasor-test-store-1`.

```graphql
query BatchLookupNodes {
  nodes(ids: ["gid://shopify/Product/111", "gid://shopify/Product/222"]) {
    id
    ... on Product {
      title
      availableForSale
    }
  }
}
```

---

### 2.14 articles & blogs — Editorial Content
* **Purpose:** Fetch editorial stories, style lookbooks, and fashion blog posts.
* **Verified Status:** ✅ Active on `rasor-test-store-1`.

```graphql
query GetBlogArticles {
  articles(first: 20, sortKey: PUBLISHED_AT, reverse: true) {
    edges {
      node {
        id
        handle
        title
        publishedAt
        excerpt
        image {
          url
          altText
        }
        author {
          name
        }
        blog {
          handle
          title
        }
      }
    }
  }
}
```

---

### 2.15 pages — Static Store Pages
* **Purpose:** Fetch static information pages (About Us, Size Charts, Contact).
* **Verified Status:** ✅ Active on `rasor-test-store-1`.

```graphql
query GetStaticPages {
  pages(first: 10) {
    edges {
      node {
        id
        handle
        title
        body
      }
    }
  }
}
```

---

### 2.16 sellingPlanGroups — Subscription Plans
* **Purpose:** Retrieve subscription cadence and recurring order discounts.
* **Verified Status:** ✅ Active on `rasor-test-store-1`.

---

### 2.17 urlRedirects — URL Routing Mappings
* **Purpose:** Query merchant routing redirects to resolve deprecated URLs.
* **Verified Status:** ✅ Active on `rasor-test-store-1`.

---

## 3. Mutations (Write Operations)

### 3.1 Cart Mutations

#### 3.1.1 cartCreate — Initialize Shopping Cart
* **Purpose:** Initiates a new cart session and generates the hosted `checkoutUrl`.
* **Standard:** This replaces the deprecated `checkoutCreate` API.
* **Verified Status:** ✅ Active on `rasor-test-store-1`.

```graphql
mutation CreateNewCart {
  cartCreate(input: {
    lines: [
      {
        quantity: 1
        merchandiseId: "gid://shopify/ProductVariant/4455667788"
      }
    ]
    attributes: [
      { key: "source", value: "rasor-agent" }
      { key: "ap2_mandate_id", value: "man_live_987654" }
    ]
    note: "Rasor AI Autonomous Session"
  }) {
    cart {
      id
      checkoutUrl
      totalQuantity
      cost {
        totalAmount {
          amount
          currencyCode
        }
      }
      lines(first: 10) {
        edges {
          node {
            id
            quantity
            merchandise {
              ... on ProductVariant {
                id
                title
                product {
                  title
                }
                price {
                  amount
                  currencyCode
                }
              }
            }
          }
        }
      }
    }
    userErrors {
      field
      message
    }
  }
}
```

> [!TIP]
> **Persistent Identifiers:** Always persist `cart.id`. It is strictly required for all subsequent item additions, quantity modifications, and address attachments.

---

#### 3.1.2 cartLinesAdd — Append Garments to Cart
* **Purpose:** Add additional variants to an active cart session.
* **Verified Status:** ✅ Active on `rasor-test-store-1`.

```graphql
mutation AppendLinesToCart {
  cartLinesAdd(
    cartId: "gid://shopify/Cart/abc123456789"
    lines: [
      { quantity: 2, merchandiseId: "gid://shopify/ProductVariant/67890" }
      { quantity: 1, merchandiseId: "gid://shopify/ProductVariant/11111" }
    ]
  ) {
    cart {
      id
      totalQuantity
      cost {
        totalAmount {
          amount
          currencyCode
        }
      }
    }
    userErrors {
      field
      message
      code
    }
  }
}
```

---

#### 3.1.3 cartLinesRemove — Evict Line Items
* **Purpose:** Remove depleted or swapped items during pre-payment candidate buffer recovery.
* **Verified Status:** ✅ Active on `rasor-test-store-1`.

```graphql
mutation RemoveCartLines {
  cartLinesRemove(
    cartId: "gid://shopify/Cart/abc123456789"
    lineIds: ["gid://shopify/CartLine/line1", "gid://shopify/CartLine/line2"]
  ) {
    cart {
      id
      totalQuantity
      cost {
        totalAmount {
          amount
        }
      }
    }
    userErrors {
      field
      message
    }
  }
}
```

---

#### 3.1.4 cartLinesUpdate — Modify Variant Quantities
* **Purpose:** Adjust line quantities or hot-swap variant sizing.
* **Verified Status:** ✅ Active on `rasor-test-store-1`.

```graphql
mutation UpdateLineQuantity {
  cartLinesUpdate(
    cartId: "gid://shopify/Cart/abc123456789"
    lines: [{ id: "gid://shopify/CartLine/line1", quantity: 3 }]
  ) {
    cart {
      id
      totalQuantity
    }
    userErrors {
      field
      message
    }
  }
}
```

---

#### 3.1.5 cartNoteUpdate — Attach Autonomous Agent Notes
* **Purpose:** Add structured reasoning metadata to the cart for order tracking.
* **Verified Status:** ✅ Active on `rasor-test-store-1`.

```graphql
mutation UpdateCartOrderNote {
  cartNoteUpdate(
    cartId: "gid://shopify/Cart/abc123456789"
    note: "Size: XL | Color: Jet Black | Protocol: AP2 Mandate | Agent: Rasor 2.0"
  ) {
    cart {
      id
      note
    }
    userErrors {
      field
      message
    }
  }
}
```

---

#### 3.1.6 cartDiscountCodesUpdate — Apply Promotional Vouchers
* **Purpose:** Apply or replace discount coupons.
* **Verified Status:** ✅ Active on `rasor-test-store-1`.

```graphql
mutation ApplyPromotionalDiscounts {
  cartDiscountCodesUpdate(
    cartId: "gid://shopify/Cart/abc123456789"
    discountCodes: ["AGENTIC10", "FREESHIP"]
  ) {
    cart {
      id
      discountCodes {
        code
        applicable
      }
      cost {
        totalAmount {
          amount
        }
      }
    }
    userErrors {
      field
      message
    }
  }
}
```

---

#### 3.1.7 cartBuyerIdentityUpdate — Attach Shopper & Shipping Address
* **Purpose:** Pre-populates contact details and destination address on the Shopify checkout.
* **Verified Status:** ✅ Active on `rasor-test-store-1`.

```graphql
mutation BindBuyerIdentityAndAddress {
  cartBuyerIdentityUpdate(
    cartId: "gid://shopify/Cart/abc123456789"
    buyerIdentity: {
      email: "shopper@example.com"
      phone: "+919876543210"
      countryCode: IN
      deliveryAddressPreferences: [{
        deliveryAddress: {
          firstName: "Vikas"
          lastName: "Sharma"
          address1: "123 MG Road"
          city: "Bangalore"
          province: "Karnataka"
          country: "India"
          zip: "560001"
        }
      }]
    }
  ) {
    cart {
      id
      checkoutUrl
      buyerIdentity {
        email
        phone
      }
    }
    userErrors {
      field
      message
    }
  }
}
```

---

#### 3.1.8 cartAttributesUpdate — Attach Session Metadata
* **Purpose:** Attach cryptographic hashes and audit tracking variables to the cart object.
* **Verified Status:** ✅ Active on `rasor-test-store-1`.

```graphql
mutation AttachCartAuditMetadata {
  cartAttributesUpdate(
    cartId: "gid://shopify/Cart/abc123456789"
    attributes: [
      { key: "agent_session_id", value: "rasor_sess_89a7f" }
      { key: "ap2_mandate_hash", value: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" }
      { key: "candidate_buffer_swaps", value: "1" }
    ]
  ) {
    cart {
      id
      attributes {
        key
        value
      }
    }
    userErrors {
      field
      message
    }
  }
}
```

---

#### 3.1.9 cartGiftCardCodesUpdate — Apply Stored Value Codes
* **Purpose:** Apply stored-value gift cards to offset the payable cart balance.
* **Verified Status:** ✅ Active on `rasor-test-store-1`.

```graphql
mutation ApplyGiftCardCode {
  cartGiftCardCodesUpdate(
    cartId: "gid://shopify/Cart/abc123456789"
    giftCardCodes: ["GC-9921-4412-8819"]
  ) {
    cart {
      id
      cost {
        totalAmount {
          amount
        }
      }
    }
    userErrors {
      field
      message
    }
  }
}
```

---

### 3.2 Customer Authentication Mutations

| Mutation | Description | Verified Scope |
| :--- | :--- | :--- |
| `customerCreate` | Register customer account with email and password | `unauthenticated_write_customers` |
| `customerAccessTokenCreate` | Generate JWT access token from email/password credentials | Unauthenticated |
| `customerAccessTokenDelete` | Revoke active access token (logout) | Unauthenticated |
| `customerAccessTokenRenew` | Extend expiration TTL of an active access token | Unauthenticated |
| `customerUpdate` | Update name, phone, or marketing acceptance flags | `unauthenticated_write_customers` |
| `customerRecover` | Send password reset email | Unauthenticated |
| `customerReset` | Finalize password change with reset token | Unauthenticated |

#### Example: Customer Registration (`customerCreate`)
```graphql
mutation RegisterCustomerAccount {
  customerCreate(input: {
    firstName: "Arjun"
    lastName: "Mehta"
    email: "arjun.mehta@example.com"
    password: "SecurePassword2026!"
    acceptsMarketing: true
  }) {
    customer {
      id
      email
      firstName
      lastName
    }
    customerUserErrors {
      field
      message
      code
    }
  }
}
```

#### Example: Customer Login (`customerAccessTokenCreate`)
```graphql
mutation LoginCustomer {
  customerAccessTokenCreate(input: {
    email: "arjun.mehta@example.com"
    password: "SecurePassword2026!"
  }) {
    customerAccessToken {
      accessToken
      expiresAt
    }
    customerUserErrors {
      field
      message
      code
    }
  }
}
```

#### 3.2.7 Customer Address Mutations
Storefront API provides four mutations to manage customer shipping records:
* `customerAddressCreate`: Attach a new address to a customer profile.
* `customerAddressUpdate`: Modify existing street, city, or PIN code.
* `customerAddressDelete`: Remove an obsolete address.
* `customerDefaultAddressUpdate`: Designate an address ID as default.

```graphql
mutation AddCustomerShippingAddress {
  customerAddressCreate(
    customerAccessToken: "VALID_CUSTOMER_ACCESS_TOKEN"
    address: {
      firstName: "Arjun"
      lastName: "Mehta"
      address1: "123 MG Road"
      city: "Bangalore"
      province: "Karnataka"
      country: "India"
      zip: "560001"
      phone: "+919876543210"
    }
  ) {
    customerAddress {
      id
      address1
      city
      zip
    }
    customerUserErrors {
      field
      message
    }
  }
}
```

---

### 3.3 Deprecated Mutations

> [!CAUTION]
> **Deprecated Checkout Mutations:** Do **NOT** use legacy `checkout*` mutations in new code. They are slated for sunset and do not support modern Shopify functions, server-side discounts, or bundling.

```
✗ checkoutCreate                → Migrate to cartCreate
✗ checkoutLineItemsAdd          → Migrate to cartLinesAdd
✗ checkoutLineItemsRemove       → Migrate to cartLinesRemove
✗ checkoutLineItemsUpdate       → Migrate to cartLinesUpdate
✗ checkoutEmailUpdate           → Migrate to cartBuyerIdentityUpdate
✗ checkoutShippingAddressUpdate → Migrate to cartBuyerIdentityUpdate
```

---

## 4. Directives & Advanced Storefront Patterns

### 4.1 @inContext Directive — Localization & Presentment Currencies
The `@inContext` directive localizes pricing, inventory availability, and content across international borders:

```graphql
query GetLocalizedCatalog @inContext(country: IN, language: EN) {
  products(first: 10) {
    edges {
      node {
        title
        variants(first: 1) {
          edges {
            node {
              price {
                amount
                currencyCode
              }
            }
          }
        }
      }
    }
  }
}
```

* **Supported Country Codes:** `IN`, `US`, `GB`, `AE`, `SG`, `AU`, `CA`, `DE`, `FR`, etc.
* **Supported Languages:** `EN`, `HI`, `FR`, `DE`, etc.

---

### 4.2 Cursor-Based Pagination Standard
All list queries in the Storefront API enforce cursor-based pagination:

```graphql
query ForwardPagination {
  products(first: 20, after: "eyJsYXN0X2lkIjo3ODkwMTJ9") {
    pageInfo {
      hasNextPage
      hasPreviousPage
      startCursor
      endCursor
    }
    edges {
      cursor
      node {
        id
        title
      }
    }
  }
}
```

---

### 4.3 Storefront-Accessible Metafields
To read custom attributes (e.g. fabric specifications, wash care, character franchise tags), metafields must be configured in Shopify Admin as **Storefront Accessible**:

```graphql
query GetProductMetafields {
  product(handle: "batman-oversized-hoodie") {
    metafields(identifiers: [
      { namespace: "custom", key: "fabric_composition" }
      { namespace: "custom", key: "care_instructions" }
      { namespace: "custom", key: "character_lore" }
    ]) {
      key
      value
      type
    }
  }
}
```

---

### 4.4 Asynchronous Bulk Operations
With `unauthenticated_write_bulk_operations` and `unauthenticated_read_bulk_operations` enabled, large catalog snapshots can be retrieved asynchronously without rate limits.

---

## 5. Rasor Implementation Architecture

### 5.1 5-Tier Progressive Retrieval Strategy
In Rasor's `src/data/shopify_api.py`, the `ShopifyCatalogProvider` executes an autonomous 5-tier fallback cascade:

```
Tier 1: products(query: "keywords AND product_type:TYPE AND tag:GENDER")
   │ (Zero results or network timeout)
   ▼
Tier 2: search(query: "keywords", prefix: LAST, types: [PRODUCT])
   │ (Zero results or full-text miss)
   ▼
Tier 3: Per-Term Union (splits query tokens and unions results)
   │ (Zero overlap)
   ▼
Tier 4: Category-Only Predicate (product_type:TYPE)
   │ (Zero catalog matches)
   ▼
Tier 5: Broad Fallback (available_for_sale:true)
```

#### Client-Side Price Filtering
Because `variants.price:<=N` is an Admin-only predicate that silently returns 0 records on the Storefront API, Rasor fetches candidates matching the semantic predicates and applies client-side mathematical filtering:

```python
# Client-side price guard in src/data/shopify_api.py
filtered_candidates = [
    item for item in raw_candidates 
    if item["price"] <= max_budget
]
```

---

### 5.2 Headless Cart & AP2 Mandate Pipeline
Rasor's checkout flow follows a 5-step programmatic sequence:

1. **Variant Resolution:** Extracts the in-stock variant GID matching the requested size token (`S`, `M`, `L`, `XL`, `XXL`).
2. **Cart Creation (`cartCreate`):** Submits variant GID and receives authoritative `cart.id` and hosted `checkoutUrl`.
3. **Buyer Identity Binding (`cartBuyerIdentityUpdate`):** Injects customer email, phone, and delivery address.
4. **Mandate Audit Attachment (`cartAttributesUpdate`):** Appends AP2 mandate identifier and deterministic SHA-256 cart payload hash.
5. **Settlement Route:**
   - **Track A (Human Present):** Redirects user to hosted `checkoutUrl` or launches desktop Razorpay modal.
   - **Track B (Autonomous S2S):** Executes programmatic tokenized settlement via backend payment rails and syncs order to Shopify Admin REST API (`financial_status: paid`).

---

### 5.3 Production Credentials & Environment Setup

#### Environment Configuration (`.env`):
```ini
SHOPIFY_DOMAIN=rasor-test-store-1.myshopify.com
SHOPIFY_STOREFRONT_API_VERSION=2024-04

# Storefront Access Token (32-character hex key for Storefront GraphQL):
SHOPIFY_STOREFRONT_TOKEN=6a1c1b2f3f1fafd8afc7040ed4e19307
# Alias supported across Rasor codebase:
SHOPIFY_STOREFRONT_ACCESS_TOKEN=6a1c1b2f3f1fafd8afc7040ed4e19307

# Shopify Admin REST API Token (shpat_... write_orders scope, NOT Storefront):
SHOPIFY_ADMIN_TOKEN=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
```

#### Diagnostic cURL Probes:

**Probe 1: Via Rasor Gateway GraphQL Proxy (Recommended — Zero CORS, Managed Token):**
```bash
curl -X POST http://localhost:8000/api/shopify/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "query { shop { name currencyCode } }"}'
```

**Probe 2: Direct to Shopify Storefront API:**
```bash
curl -X POST https://rasor-test-store-1.myshopify.com/api/2024-04/graphql.json \
  -H "Content-Type: application/json" \
  -H "X-Shopify-Storefront-Access-Token: $SHOPIFY_STOREFRONT_TOKEN" \
  -d '{"query": "query { shop { name currencyCode } }"}'
```

---

## 6. API Quick Reference Cheat Sheet

### Queries Matrix (18 Operations)

| Query Operation | Primary Purpose | Scope Required | Verification Status |
| :--- | :--- | :--- | :---: |
| [`products`](#21-products--catalog-browsing--filtered-listings) | Filtered product catalog & pagination (Tier 1) | `unauthenticated_read_product_listings` | ✅ Verified Live |
| [`product`](#22-product--single-product-inspection-by-id-or-handle) | Deep single product details by handle or GID | `unauthenticated_read_product_listings` | ✅ Verified Live |
| [`search`](#23-search--full-text-relevance-search) | Relevance-ranked full-text search (Tier 2) | `unauthenticated_read_product_listings` | ✅ Verified Live |
| [`predictiveSearch`](#24-predictivesearch--typeahead-autocomplete) | Real-time typeahead suggestions | `unauthenticated_read_product_listings` | ✅ Verified Live |
| [`collections`](#25-collections--collection-catalog-list) | List all store collection handles & titles | `unauthenticated_read_product_listings` | ✅ Verified Live |
| [`collection`](#26-collection--products-by-collection-handle) | Retrieve products inside one collection | `unauthenticated_read_product_listings` | ✅ Verified Live |
| [`cart`](#27-cart--cart-state--checkout-url-inspection) | Retrieve live cart state, pricing & checkout URL | `unauthenticated_read_checkouts` | ✅ Verified Live |
| [`customer`](#28-customer--authenticated-customer-profile--orders) | Customer profile, addresses, and past orders | `unauthenticated_read_customers` | ✅ Verified Live |
| [`shop`](#29-shop--store-metadata--policies) | Store name, currencies, policies | None (Public) | ✅ Verified Live |
| [`localization`](#210-localization--country-currency--language-context) | Country, currency, and language context | None (Public) | ✅ Verified Live |
| [`metaobject`](#211-metaobject--metaobjects--custom-cms-metadata) | Fetch custom structured CMS entities by ID | `unauthenticated_read_metaobjects` | ✅ Verified Live |
| [`metaobjects`](#211-metaobject--metaobjects--custom-cms-metadata) | List metaobjects filtered by entity type | `unauthenticated_read_metaobjects` | ✅ Verified Live |
| [`productRecommendations`](#212-productrecommendations--algorithmic-suggestions) | ML-driven "you may also like" suggestions | `unauthenticated_read_product_listings` | ✅ Verified Live |
| [`node`](#213-node--nodes--generic-gid-lookup) | Polymorphic lookup of single entity by GID | Varies by entity | ✅ Verified Live |
| [`nodes`](#213-node--nodes--generic-gid-lookup) | Batch polymorphic lookup by GID list | Varies by entity | ✅ Verified Live |
| [`articles`](#214-articles--blogs--editorial-content) | Editorial and blog post listings | `unauthenticated_read_content` | ✅ Verified Live |
| [`blogs`](#214-articles--blogs--editorial-content) | List store blogs | `unauthenticated_read_content` | ✅ Verified Live |
| [`pages`](#215-pages--static-store-pages) | Static store pages (FAQ, sizing, terms) | `unauthenticated_read_content` | ✅ Verified Live |
| [`sellingPlanGroups`](#216-sellingplangroups--subscription-plans) | Subscription cadence and recurring plans | `unauthenticated_read_selling_plans` | ✅ Verified Live |
| [`urlRedirects`](#217-urlredirects--url-routing-mappings) | Storefront URL redirect lookup | None (Public) | ✅ Verified Live |

---

### Mutations Matrix (20 Operations)

| Mutation Operation | Primary Purpose | Scope Required | Verification Status |
| :--- | :--- | :--- | :---: |
| [`cartCreate`](#311-cartcreate--initialize-shopping-cart) | Initialize new cart session & get checkout URL | `unauthenticated_write_checkouts` | ✅ Verified Live |
| [`cartLinesAdd`](#312-cartlinesadd--append-garments-to-cart) | Append product variants to active cart | `unauthenticated_write_checkouts` | ✅ Verified Live |
| [`cartLinesRemove`](#313-cartlinesremove--evict-line-items) | Evict items from active cart | `unauthenticated_write_checkouts` | ✅ Verified Live |
| [`cartLinesUpdate`](#314-cartlinesupdate--modify-variant-quantities) | Modify quantity of an existing line item | `unauthenticated_write_checkouts` | ✅ Verified Live |
| [`cartNoteUpdate`](#315-cartnoteupdate--attach-autonomous-agent-notes) | Set order note on cart payload | `unauthenticated_write_checkouts` | ✅ Verified Live |
| [`cartDiscountCodesUpdate`](#316-cartdiscountcodesupdate--apply-promotional-vouchers) | Apply or remove promotional discount codes | `unauthenticated_write_checkouts` | ✅ Verified Live |
| [`cartBuyerIdentityUpdate`](#317-cartbuyeridentityupdate--attach-shopper--shipping-address) | Bind email, phone, and delivery address | `unauthenticated_write_checkouts` | ✅ Verified Live |
| [`cartAttributesUpdate`](#318-cartattributesupdate--attach-session-metadata) | Store custom audit key-value pairs on cart | `unauthenticated_write_checkouts` | ✅ Verified Live |
| [`cartGiftCardCodesUpdate`](#319-cartgiftcardcodesupdate--apply-stored-value-codes) | Apply gift card stored-value payment | `unauthenticated_write_checkouts` | ✅ Verified Live |
| [`customerCreate`](#321-customercreate--account-registration) | Register new customer account | `unauthenticated_write_customers` | ✅ Verified Live |
| [`customerAccessTokenCreate`](#322-customeraccesstokencreate--customer-login) | Login and obtain customer JWT session token | None (Public) | ✅ Verified Live |
| [`customerAccessTokenDelete`](#323-customeraccesstokendelete--customer-logout) | Revoke customer access token (logout) | None (Public) | ✅ Verified Live |
| [`customerAccessTokenRenew`](#324-customeraccesstokenrenew--session-renewal) | Refresh customer session before expiration | None (Public) | ✅ Verified Live |
| [`customerUpdate`](#325-customerupdate--profile-update) | Modify customer profile information | `unauthenticated_write_customers` | ✅ Verified Live |
| [`customerRecover`](#326-customerrecover--customerreset--password-recovery) | Trigger account recovery password email | None (Public) | ✅ Verified Live |
| [`customerReset`](#326-customerrecover--customerreset--password-recovery) | Finalize password reset with secret token | None (Public) | ✅ Verified Live |
| [`customerAddressCreate`](#327-customer-address-mutations) | Save new delivery address to profile | `unauthenticated_write_customers` | ✅ Verified Live |
| [`customerAddressUpdate`](#327-customer-address-mutations) | Update existing delivery address | `unauthenticated_write_customers` | ✅ Verified Live |
| [`customerAddressDelete`](#327-customer-address-mutations) | Remove saved delivery address | `unauthenticated_write_customers` | ✅ Verified Live |
| [`customerDefaultAddressUpdate`](#327-customer-address-mutations) | Set default shipping address for checkout | `unauthenticated_write_customers` | ✅ Verified Live |

---

## 7. FastAPI Gateway REST Integration Mapping

The table below bridges the underlying Storefront GraphQL operations to their exposing endpoints in the **FastAPI Gateway** ([API_SPECIFICATION.md](API_SPECIFICATION.md)):

| Shopify GraphQL / REST Operation | Exposing Gateway REST Endpoint | Implementation Provider | Specification Link |
| :--- | :--- | :--- | :--- |
| `query products(query: ...)` | `POST /api/search` | `ShopifyCatalogProvider` | [API Spec §2.B](API_SPECIFICATION.md#b-search-catalog--discovery) |
| `query product(id: ...)` / `query products(query: "id:...")` | `POST /api/products/by-ids` | `ShopifyCatalogProvider` | [API Spec §2.B](API_SPECIFICATION.md#b-search-catalog--discovery) |
| `mutation cartCreate($input: CartInput!)` | `POST /api/cart/create` | `ShopifyCartProvider` | [API Spec §2.F](API_SPECIFICATION.md#f-headless-cart--storefront-mutation) |
| `mutation cartLinesAdd($cartId: ID!, $lines: ...)` | `POST /api/cart/add` | `ShopifyCartProvider` | [API Spec §2.F](API_SPECIFICATION.md#f-headless-cart--storefront-mutation) |
| `POST /admin/api/2024-04/orders.json` | `POST /api/shopify/sync` | `ShopifyAdminProvider` | [API Spec §2.I](API_SPECIFICATION.md#i-settlement-background-reconciler--audit-ledger) |
| `GET /admin/api/2024-04/orders.json` | `GET /api/shopify/orders` | `ShopifyAdminProvider` | [API Spec §2.I](API_SPECIFICATION.md#i-settlement-background-reconciler--audit-ledger) |

---

*Authored for the Rasor Autonomous Agentic Commerce Engine. Live validated against Shopify Storefront API version 2024-04.*
