# Design System Specification: Editorial Financial Intelligence

## 1. Overview & Creative North Star
**The Creative North Star: "The Digital Architect"**
In a world of cluttered financial dashboards, this design system acts as a high-end curator. It rejects the "spreadsheet-as-a-service" aesthetic in favor of a sophisticated, editorial layout that mimics a premium financial journal. 

We move beyond "Standard SaaS" by employing **Intentional Asymmetry**. Rather than a rigid, centered grid, we use wide gutters and offset headers to guide the eye. By layering surfaces rather than boxing them in, we create a sense of infinite depth—positioning the platform not just as a tool, but as an authoritative partner in wealth management.

---

## 2. Colors & Surface Philosophy
The palette is rooted in the "Deep Slate" of institutional trust, punctuated by "Electric Intelligence" blue.

### The "No-Line" Rule
**Strict Mandate:** Traditional 1px solid borders (#D1D5DB style) are prohibited for sectioning. 
Hierarchy must be defined through **Background Color Shifts**. To separate a sidebar from a main feed, transition from `surface` (#f7f9fb) to `surface-container-low` (#f2f4f6). Boundaries should be felt, not seen.

### Surface Hierarchy & Nesting
Treat the UI as a physical stack of fine vellum.
*   **Base Layer:** `surface` (#f7f9fb) – The "table" everything sits on.
*   **Secondary Content:** `surface-container-low` (#f2f4f6) – Used for grouping related data.
*   **Focus Elements:** `surface-container-lowest` (#ffffff) – Reserved for the highest priority data cards, creating a "lift" through contrast.

### The "Glass & Gradient" Rule
To escape the flat, "Bootstrap" look, use Glassmorphism for floating overlays (e.g., Command Palettes or Chat Bubbles).
*   **Token:** `surface-container-lowest` at 80% opacity with a `24px` backdrop-blur.
*   **Signature Textures:** Main CTAs should use a subtle linear gradient: `primary` (#000000) to `primary_container` (#131b2e) at 135°. This adds a tactile, metallic sheen to financial actions.

---

## 3. Typography
We utilize a dual-typeface system to balance "Data" with "Authority."

*   **Display & Headlines (Manrope):** A geometric sans-serif that feels modern yet sturdy. Use `display-lg` (3.5rem) with `-0.04em` tracking for a bold, editorial "Hero" moment.
*   **Body & Titles (Inter):** The workhorse. High legibility for dense financial figures.
    *   **Financial Data:** Always use `body-md` (0.875rem) with `tabular-nums` OpenType features enabled to ensure decimal points align vertically in tables.
*   **Hierarchy Tip:** Contrast a `headline-sm` (1.5rem) in Manrope with a `label-sm` (0.6875rem) in Inter All-Caps for metadata. The scale jump creates instant premium "vibe."

---

## 4. Elevation & Depth
Depth is a functional tool, not a decoration.

*   **Tonal Layering:** Avoid shadows for static cards. Instead, place a `surface-container-lowest` card on a `surface-container-low` background. This is "Zero-Elevation Depth."
*   **Ambient Shadows:** For active states or modals, use an "Atmospheric Shadow":
    *   `0px 20px 40px rgba(15, 23, 42, 0.06)`
    *   The shadow is tinted with our Slate primary, making it feel like a natural part of the environment.
*   **The "Ghost Border":** If a data table requires containment, use the `outline_variant` (#c6c6cd) at **15% opacity**. It should be a mere suggestion of a line.

---

## 5. Components

### The Conversational Interface (AI)
The ChatGPT-style interface is the "Intelligence Layer." 
*   **The Bubble:** User messages are `primary_container` (#131b2e) with `on_primary_container` text. AI responses sit directly on the `surface` with no bubble, distinguished only by a small `secondary` (#0058be) spark icon.
*   **The Input:** A floating `surface-container-lowest` bar with a 12px blur glass effect.

### Data Tables (The "Editorial Grid")
*   **Padding:** Use Spacing Scale `4` (1.4rem) for vertical cell padding. Financial data needs "air" to be digestible.
*   **No Dividers:** Remove horizontal lines. Use a `surface-container-high` background on hover to highlight the active row.
*   **Alignment:** Labels are Left-Aligned; Currency/Numbers are Right-Aligned; Status Chips are Centered.

### Buttons & Interaction
*   **Primary:** Solid `primary` (#000000) with `lg` (0.5rem) roundedness.
*   **Secondary:** `surface-container-high` background with `on_surface` text. No border.
*   **States:** On `hover`, increase the background brightness by 5%. On `active` (click), scale the component to 98% to provide tactile feedback.

### Cards
*   **Rule:** Forbid the use of dividers within cards. Use Spacing Scale `6` (2rem) to separate a header from the body content. Use `surface-container-highest` for a thin 4px "accent bar" at the top of a card to denote category colors.

---

## 6. Do's and Don'ts

### Do
*   **Do** use `24` (8.5rem) spacing for top-level section margins to create a high-end, spacious feel.
*   **Do** use `secondary` (#0058be) sparingly for "Success" or "Action" highlights.
*   **Do** use `tertiary_fixed` (#fcdeb5) for subtle warnings or "Pending" states—it feels more sophisticated than standard orange.

### Don't
*   **Don't** use pure black (#000000) for text. Use `on_surface` (#191c1e) to reduce eye strain.
*   **Don't** use 100% opaque borders. Always use the Ghost Border approach (10-20% opacity).
*   **Don't** cram multiple charts into a single row. Limit to two to maintain the editorial integrity of the layout.