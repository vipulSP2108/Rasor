# Rasor: Future Prospects, Machine Learning Backlog & Research Register

A technical research register and engineering roadmap detailing long-term machine learning enhancements, offline data pipelines, and evaluated concepts that were intentionally deferred or rejected.

---

## 1. High-Potential Evolutionary Prospects (Data & Infrastructure Dependent)

These architectural enhancements are scheduled for implementation as live traffic volume, user telemetry, and background infrastructure scale:

### 1.1 Machine-Learned Gradient-Boosted Re-Ranker (GBDT / LightGBM)
* **Current Baseline:** Declarative configuration (`PAIRING_WEIGHT_CONFIG` in `src/agent/semantic_color_engine.py`) combining five base perceptual features (`hue_harmony`, `value_contrast`, `chroma_comp`, `neutral_bonus`, `pattern_echo`).
* **The Evolution:**
  * Once the platform logs several thousand complete user sessions, behavioral telemetry is aggregated:
    - Complete-the-look click-through rates.
    - Co-purchase frequencies from shopping carts.
    - Post-purchase return and exchange rates for coordinated ensembles.
  * Train a lightweight Gradient-Boosted Decision Tree (LightGBM) per pairing type using the 5 base perceptual features, price ratio, and seasonal tags as inputs.
  * **Benefit:** Retains complete algorithmic explainability while allowing empirical purchase behavior to optimize the hand-tuned weight priors over time.

### 1.2 Offline Pre-Computed Image K-Means & Color Embeddings
* **Current Baseline:** Catalog searches map store color tags (e.g. `"Black"`, `"Navy"`, `"Olive"`) directly to canonical LCh centroids at 0ms latency. Image K-Means is strictly reserved for user-uploaded photos via the `+` attachment button.
* **The Evolution:**
  * Running K-Means clustering dynamically during a live search request across 40 candidate images introduces a 3–5 second latency penalty.
  * **The Solution:** Move product image K-Means to an **Offline Ingestion Worker / Scheduled Cron**.
  * During catalog synchronization, background workers download product imagery, apply grab-cut background masking, execute 3-cluster K-Means in CIELAB space, and store pre-computed dominant LCh centroids and pixel area percentages directly in the database:
    ```json
    {
      "color_centroids": [
        {"L": 18.2, "C": 25.4, "h": 260.1, "area_pct": 0.72},
        {"L": 92.0, "C": 2.1,  "h": 0.0,   "area_pct": 0.28}
      ]
    }
    ```
  * At runtime, `pattern_echo` evaluates pre-computed centroids instantly with zero network download latency.

### 1.3 Ingestion-Time Semantic Enrichment vs. Runtime Parsing
* **Current Baseline:** Hybrid runtime parsing (deterministic preprocessor + LLM intent normalization + regex fallbacks).
* **The Evolution:**
  * Run offline batch LLM enrichment across the merchant catalog to pre-tag:
    - Aesthetic vibe (Streetwear, Minimalist, Old Money, Athleisure).
    - Silhouette fit (Drop-shoulder boxy, Tapered, Wide-leg).
    - Occasion tags (Party, Casual Friday, Gym, Lounge).
    - Character and franchise IP hierarchy.
  * Eliminates runtime ambiguity and allows candidate ranking to query structured metadata columns directly.

### 1.4 Hardware-Secured WebAuthn AP2 Mandate Signing
* **Current Baseline:** Software-level SHA-256 cart mandate hashing and tokenized vault storage.
* **The Evolution:**
  * Integrate WebAuthn / Passkeys for hardware-backed enclave signing (FIDO2 / Secure Enclave) when establishing high-value AP2 intent mandates ($> ₹10,000$).
  * The cryptographic signature proves user presence at the hardware layer, satisfying Tier 4 financial compliance without recurring SMS OTP friction.

### 1.5 Edge-ASR via WebAssembly Whisper (Private Offline Voice Engine)
* **Current Baseline:** Client-side speech recognition relies on the browser-native Web Speech API (`webkitSpeechRecognition`), which delegates audio transcription to vendor cloud servers and is vulnerable to network jitter and browser permission quirks.
* **The Evolution:**
  * Package a quantized on-device Whisper model (Whisper Tiny quantized to INT8, ~39 MB) compiled to WebAssembly / ONNX Runtime running directly in the browser's background web worker.
  * **Benefit:** 100% private, offline, accent-resilient speech-to-text with zero cloud network round-trips and complete acoustic isolation for confidential vocal shopping prompts.

### 1.6 Distributed Geodesic Split-Fulfillment Mesh
* **Current Baseline:** Delivery velocity and Haversine distance are evaluated against the merchant's primary warehouse origin (e.g. Mumbai, Maharashtra).
* **The Evolution:**
  * Expand the Geodesic Logistics Agent into a multi-node routing mesh that evaluates distributed inventory across regional dark stores and multi-vendor warehouses.
  * Multi-item ensembles are programmatically split: top garments can be dispatched from a local hyper-local hub (4-hour express delivery) while specialized accessories or footwear ship via surface transit from a central hub.
  * The agent optimizes a multi-objective cost function:
    $$\min \Big(\alpha \cdot \text{Shipping Cost} + \beta \cdot \text{Delivery Time} + \gamma \cdot \text{Carbon Footprint}\Big)$$

---

## 2. Evaluated Concepts Intentionally Deferred or Rejected

These concepts were investigated and intentionally discarded due to user friction, unreliability, or prohibitive latency:

### 2.1 Camera White-Balance Calibration & Face Mesh Segmentation
* **The Concept:** Requiring users to upload a selfie, using a face mesh model to segment facial pixels, masking lips/eyes, and calibrating for camera white-balance in LAB space to infer skin undertones.
* **Why Rejected:**
  * Consumer smartphone selfies taken under warm indoor lighting (2700K incandescent or warm LED bulbs) shift cool undertones to warm yellow.
  * Without physical reference cards (such as a photographer's 18% neutral grey card), algorithmic white-balance estimation is inaccurate.
  * A confident misclassification (e.g. classifying a cool-toned user as warm and recommending muddy mustard) damages shopper trust.
  * **Our Solution:** A non-compulsory 3-question self-report quiz (Jewelry preference, Sun response, Vein color) or Monk Scale slider in `ProfilePanel.jsx`. Zero latency, 100% user-controlled, and non-intrusive.

### 2.2 Hair and Eye Contrast Depth Ratios
* **The Concept:** Factoring in natural contrast ratios between user skin depth, hair depth, and iris color to recommend high-contrast versus muted tonal palettes.
* **Why Rejected:**
  * Introducing mandatory questions regarding hair and eye depth creates high cognitive load for an estimated $<2\%$ styling improvement.
  * Over 90% of styling effectiveness is captured by **Undertone (Warm vs. Cool)** and **Depth (Monk Scale 1–10)**.

### 2.3 Runtime Computer Vision Inference on Search Streams
* **The Concept:** Running live multimodal vision models on all raw catalog images during every search query.
* **Why Rejected:**
  * Introduces 4–8 seconds of latency per query and multiplies API token costs significantly.
  * **Our Solution:** The vision scanner is strictly triggered when a `specific_visual_intent` is present, scanning only the top filtered survivors via parallel threads.

---

## 3. Protocol & Distributed Settlement Innovations

### 3.1 Interactive Aesthetic "Vibe Mapping"
Translating high-level stylistic aesthetics (*"90s retro grunge"*, *"minimalist streetwear"*, *"cyberpunk"*) into concrete LCh color palettes and silhouette parameters:
* *"Retro Grunge"* $\rightarrow$ Fit: `Oversized Boxy`, Design: `Acid Washed`, Palette: `Charcoal / Deep Maroon / Black`.
* *"Minimalist"* $\rightarrow$ Fit: `Regular Clean`, Design: `Solid`, Palette: `Off-White / Sand Beige / Dark Navy`.

### 3.2 Single-Merchant Coupon & Bundle Optimization
When an outfit bundle is assembled, the agent scans active merchant promotional schemes (e.g. *"Buy 3 for ₹1,199"*, *"Spend ₹3,000 get 20% off"* via `OfferEngine`), calculates the highest-saving discount combination, and locks the discounted total in the AP2 Cart Mandate before customer authorization.

### 3.3 Autonomous Multi-Agent Bounded Price Negotiation (UAP Peer-to-Peer)
* **The Concept:** In modern e-commerce, promotions are static and one-sided. In an Agentic Commerce Protocol (ACP) ecosystem, the shopper's buyer agent can directly negotiate transactional terms with the merchant's sales daemon:
  * *Buyer Agent:* "My user has authorized an AP2 intent mandate for an ensemble of ₹2,400 with immediate settlement. We have two items in-cart with total ₹2,550. Can your pricing agent authorize an automatic 6% bundle concession for immediate capture?"
  * *Merchant Agent:* Evaluates real-time inventory velocity, margins, and dead-stock depreciation. If margins permit, it issues a signed one-time cryptographic discount token bound to the active `CartHash`.
  * **Benefit:** Simulates real-world wholesale and bazaar price discovery autonomously while strictly bounding financial parameters on both sides.

### 3.4 Zero-Knowledge Attribute Mandates (ZK-Mandates)
* **The Concept:** Users frequently hesitate to share sensitive personal attributes—such as precise waist/chest measurements, exact annual income, or maximum bank balances—with third-party AI agents and e-commerce platforms.
* **The Solution:** Implement Zero-Knowledge Succinct Non-Interactive Arguments of Knowledge (zk-SNARKs) for mandate authorization:
  * The user's device generates a cryptographic proof:
    $$\pi = \text{ZK-Proof}\Big(\text{User Balance} \ge \text{Cart Total} \quad \land \quad \text{User Waist} \in [31^{\prime\prime}, 33^{\prime\prime}]\Big)$$
  * The merchant and payment gateway verify $\pi$ without ever learning the customer's actual bank account balance or bodily dimensions.

---

Developed for the Razorpay Agentic Commerce Hackathon 2026.
