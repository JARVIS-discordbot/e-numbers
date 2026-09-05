# Changelog

## [released]

### 📚 Data Sources (2026-09-05)
- Added the EU Food Additives API as the primary source for E-number synchronization.
- Updated the EU integration to use the `food-additives-list` endpoint with `format=json` and `api-version=v2.0`.
- Added support for the EU response fields `additive_e_code` and `additive_name`.
- Added pagination through the API's `nextLink`; the live dataset returned 412 records across 5 pages.
- Open Food Facts remains available as a fallback source and for supplementary metadata.

### 🛠️ Fixes & Reliability (2026-08-11)
- **Removed flag false-positives fixed (E14XX ranges)**:
  - Improved Open Food Facts additive tag parsing to correctly handle range-style tags (like `E14XX`)
  - Added prefix-based matching so `E14XX` maps to specific codes such as `E1414`, `E1420`, etc.
  - Prevents incorrect `removed: true` flags for valid modified starch entries

- **OFF sync fallback added**:
  - Primary sync still uses `https://world.openfoodfacts.org/facets/additives.json`
  - Added automatic fallback to `https://static.openfoodfacts.org/data/taxonomies/additives.json` when the primary endpoint is unavailable (e.g. HTTP 503)
  - Normalizes fallback taxonomy format into the same additive shape used by sync logic

- **Sync status visibility on main UI**:
  - Added a live sync status panel showing:
    - last Open Food Facts sync run time
    - next scheduled sync time
    - last result (matched count or failure message)
  - Status auto-refreshes periodically from `/api/update_status`

- **Sync status persistence across restarts**:
  - Added persisted status storage (`sync_status.json`)
  - `last_off_sync_*` fields now survive service restarts instead of resetting to `null`
  - `/api/update_status` now includes scheduler-derived `next_off_sync_due`

- **Removed-tag accuracy improvements**:
  - `removed` is now only set when sync uses the **primary** OFF additives endpoint
  - Fallback taxonomy syncs no longer aggressively mark unmatched additives as removed
  - Added `removed_reason`, `removed_last_checked`, and `removed_source` metadata for traceability

---

### 🚀 Features
- **API Resilience**:  
  - Fixed API endpoint issue  
  - Added fallback to load from local JSON when Flask API isn't running  
  - Created proper workflows for both Vite dev server and Flask API  
  - App now works regardless of whether the Flask API is running, improving development and demo robustness

- **Data Export**:  
  - Added CSV export for filtered results  
  - Keyboard shortcut: `Ctrl+E` to export  

- **Keyboard Shortcuts**:  
  - `Ctrl+K` – Focus search  
  - `Escape` – Clear search  
  - `Ctrl+E` – Export CSV  
  - `Ctrl+D` – Toggle charts  
  - Arrow keys – Navigate table cells  

- **Tooltips & UX Enhancements**:  
  - Added helpful tooltips throughout the UI  
  - Improved error handling and mobile responsiveness  
  - Updated search placeholder to display relevant keyboard shortcut

- **Simple Server Startup**:  
  - Added script to start the server easily

---

### 📊 Data Visualization
- Interactive doughnut chart showing E-number distribution by category  
- Dynamic chart updates based on search filters  
- Toggle visibility with a `Ctrl+D` shortcut

---

### 📱 Mobile Responsiveness
- Improved chart layout for small screens  
- Better spacing, sizing, and touch targets for mobile users

---

### ♿ Accessibility
- Skip link for screen readers  
- ARIA labels and roles throughout  
- Keyboard navigation for table cells (arrow keys)  
- Screen reader announcements for dynamic content  
- High contrast mode support  
- Respects reduced motion preferences  
- Visible focus indicators for all interactive elements

---

### 🖨️ Print-Friendly Styles
- Clean, black-and-white print layout  
- Hides interactive elements when printing  
- Displays full URLs for links  
- Optimized font sizes and spacing  
- Adds print date header  
- Page break handling

---

### 🎨 Visual Enhancements
- **Interactive Stats Dashboard**:
  - Displays total E-numbers, categories, current results, and generally safe items
- **Safety Color Indicators**:
  - 🟢 Green: Generally safe  
  - 🟡 Yellow: Use with caution  
  - 🔴 Red: Potential concerns  
  - ⚫ Gray: Unknown/insufficient data
- **Animations**:
  - Smooth slide-in for table rows  
  - Pulsing safety indicators  
  - Loading skeleton effect  
  - Gradient shimmer  
  - Hover transformations
- **Modern Design**:
  - Glassmorphism cards with backdrop blur  
  - Gradient buttons with shine effects  
  - Floating label inputs  
  - Animated gradient headers  
  - Enhanced icons
- **Polish**:
  - Staggered row animations  
  - Smooth theme transitions with scaling effects  
  - Better typography with gradient text effects  
  - Improved button hovers and focus states

---

### 📌 Notes
For full API functionality:
1. Start the **Flask API Server** workflow first
2. Start the **Dev Server**

Keyboard shortcuts:
- `Ctrl+K` – Search  
- `Escape` – Clear search  
- `Ctrl+E` – Export CSV  
- `Ctrl+D` – Toggle charts  

---
